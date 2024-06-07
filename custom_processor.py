# -*- coding: utf-8 -*-

from wasabi import Printer
from abulafia.functions import *
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
from toloka.streaming.event import AssignmentEvent
import pandas as pd
import toloka.client as toloka
import copy

# Set up Printer
msg = Printer(pretty=True, timestamp=True, hide_animation=True)


class Bucket:
    """
    This custom class holds the output data.
    """

    def __init__(self, configuration):

        self.conf = read_configuration(configuration)
        self.name = self.conf['name']

        self.data = []

    def __call__(self, event: Union[AssignmentEvent, dict, List[AssignmentEvent]] = None) -> None:

        # Each incoming object is a dictionary
        self.data.append({'image': event['input_data']['image'],
                          'ai2d_ids': event['input_data']['outlines'][0]['ai2d_id']})

        df = pd.DataFrame(self.data)

        df.to_csv(f'{self.conf["output_file"]}.tsv', sep='\t', header=True, index=False)
        msg.good('Wrote data from bucket to disk ...')



class JoinBBoxes:
    """
    This custom class joins together bounding boxes based on points placed within them.
    """
    def __init__(self, configuration, task, target):

        self.task = task
        self.conf = read_configuration(configuration)
        self.name = self.conf['name']

        self.target = target

        # Keep track of assignments that have been processed
        self.prev_assignments = set()

    def __call__(self, pool: toloka.Pool) -> None:

        # Retrieve assignments that have been submitted or accepted
        assignments = list(self.task.client.get_assignments(pool_id=pool.id,
                                                            status=[toloka.Assignment.SUBMITTED]))

        # Only begin processing if assignments are available
        if len(assignments) > 0:

            # Create a placeholder for the final data
            final_output = {}

            # Loop over assignments and check that this assignment has not been processed before
            for a in assignments:
                if a.id not in self.prev_assignments:

                    # Loop over the task and solution in the Toloka Task objects
                    for task, solution in zip(a.tasks, a.solutions):

                        # Retrieve the input and output bounding boxes from the YAML configuration
                        orig_boxes = task.input_values[self.conf['data']]
                        crowd_boxes = solution.output_values[self.conf['data']]

                        # Collect points drawn by crowdsourced workers
                        points = [box for box in crowd_boxes if box['shape'] == 'point']

                        # Reject work if workers have deleted bounding boxes
                        if (len(crowd_boxes) - len(points)) != len(orig_boxes):

                            self.task.client.reject_assignment(assignment_id=a.id,
                                                               public_comment="Your work was rejected, because you "
                                                                              "deleted some of the original bounding "
                                                                              "boxes.")
                            msg.warn(f"Rejected assignment {a.id}")

                            continue

                        # Reject work if workers have not drawn any bounding boxes
                        if len(points) == 0:

                            self.task.client.reject_assignment(assignment_id=a.id,
                                                               public_comment="Your work was rejected, because you "
                                                                              "did not draw any points")
                            msg.warn(f"Rejected assignment {a.id}")

                            continue

                        # Create a placeholder list for the original polygons as Shapely Polygons
                        orig_polys = []

                        # Convert the input polygons into Shapely Polygons
                        for box in orig_boxes:

                            if box['shape'] == 'rectangle':

                                bbox = Polygon([(box['left'], box['top']),
                                                (box['left'] + box['width'], box['top']),
                                                (box['left'] + box['width'], box['top'] + box['height']),
                                                (box['left'], box['top'] + box['height'])])
                                orig_polys.append(bbox)

                            if box['shape'] == 'polygon':

                                bbox = Polygon([(x['left'], x['top']) for x in box['points']])
                                orig_polys.append(bbox)

                        # Set up placeholders for groups of polygons and their IDs
                        group, elem_ids = [], []

                        # Loop over each point drawn by workers
                        for p in points:

                            # Convert the coordinates into a shapely Point
                            p = Point((p['left'], p['top']))

                            # Create placeholders for filtering multiple matches that result from overlapping bounding
                            # boxes (think e.g. of a point placed within a line that crosses a larger object).
                            matches, match_ids = [], []

                            # Loop over the original polygons converted into Shapely Polygons
                            for i, poly in enumerate(orig_polys):

                                # Check if the polygon contains the Point object 'p'
                                if poly.contains(p):

                                    # Append the polygon to the group
                                    matches.append(poly)
                                    match_ids.append(orig_boxes[i]['ai2d_id'])

                                # Find the source element – these can be added directly to the final lists
                                if orig_boxes[i]['label'] == 'source':

                                    group.append(poly)
                                    elem_ids.append(orig_boxes[i]['ai2d_id'])

                            # Check if there are multiple matches for the point and get the smallest polygon
                            if len(matches) > 1:

                                smallest_poly = min(matches, key=lambda box: box.area)
                                group.append(smallest_poly)
                                elem_ids.append(match_ids[matches.index(smallest_poly)])

                            else:

                                elem_ids.extend(match_ids)
                                group.extend(matches)

                        # Sort the group according to area
                        group = sorted(group, key=lambda polygon: polygon.area, reverse=True)

                        # Create an union of the shapes
                        union = unary_union([p.buffer(0) for p in group])

                        # Create a bounding box for the convex hull of the combined elements
                        unified_bbox = {'shape': 'polygon',
                                        'points': [{'left': x, 'top': y} for x, y in
                                                   union.convex_hull.exterior.coords],
                                        'ai2d_id': '+'.join(sorted(set(elem_ids)))
                                        }

                        # Get identifiers for the currently grouped elements in the dict 'final_output'
                        current_groups = [d['ai2d_id'] for sublist in final_output.values() for d in sublist]

                        if unified_bbox['ai2d_id'] not in current_groups:

                            # If the current image is not already in the dictionary, add the key and bbox
                            if task.input_values['image'] not in final_output.keys():
                                final_output[task.input_values['image']] = [unified_bbox]

                            # Otherwise, extend the existing list with the current bbox
                            else:
                                final_output[task.input_values['image']].extend([unified_bbox])

                        else:
                            pass

                        # Accept the assignment
                        self.task.client.accept_assignment(assignment_id=a.id,
                                                           public_comment="Thank you for your work!")
                        msg.warn(f"Accepted assignment {a.id}")

                        # Add current task to the list of already processed tasks
                        self.prev_assignments.add(a.id)

            # Create a placeholder for new tasks
            new_tasks = []

            for img, outlines in final_output.items():

                # Create a placeholder for labelled outlines
                labelled_outlines = []

                # Add initial labels to all outlines; set to target
                for o in outlines:

                    o["label"] = "target"

                # Create deep copies of entire outline sets
                for i in range(len(outlines)):
                    labelled_outlines.append(copy.deepcopy(outlines))

                # Add source labels to the data so that each outline is used once as source
                for i in range(len(outlines)):
                    labelled_outlines[i][i]["label"] = "source"

                # Loop over the labelled outlines and create new Tasks
                for o in labelled_outlines:

                    new_tasks.append(toloka.Task(pool_id=self.target.pool.id,
                                                 input_values={'image': img, 'outlines': o},
                                                 unavailable_for=self.task.blocklist))

            # If new tasks have been created, add them to the pool
            if len(new_tasks) > 0:

                # Create new tasks and open the pool
                self.task.client.create_tasks(new_tasks, allow_defaults=True, open_pool=True)