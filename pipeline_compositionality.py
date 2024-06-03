# -*- coding: utf-8 -*-

from abulafia.actions import Forward, Aggregate
from abulafia.task_specs import TaskSequence, SegmentationClassification, ImageSegmentation
from custom_processor import JoinBBoxes
import argparse
import json
import toloka.client as toloka


# Set up the argument parser
ap = argparse.ArgumentParser()

# Add argument for input
ap.add_argument("-c", "--creds",
                required=True,
                help="Path to a JSON file that contains Toloka credentials. "
                     "The file should have two keys: 'token' and 'mode'. "
                     "The key 'token' should contain the Toloka API key, whereas "
                     "the key 'mode' should have the value 'PRODUCTION' or 'SANDBOX' "
                     "that defines the environment in which the pipeline should be run.")

# Parse the arguments
args = vars(ap.parse_args())

# Assign arguments to variables
cred_file = args['creds']

# Read the credentials from the JSON file
with open(cred_file) as cred_f:

        creds = json.loads(cred_f.read())
        tclient = toloka.TolokaClient(creds['token'], creds['mode'])

''' CREATE THE TASKS AND PROCESSES IN THE CROWDSOURCING PIPELINE TO GENERATE DESCRIPTIONS OF COMPOSITIONALITY IN DIAGRAMS '''


''' PHASE 1 '''
# Task 1: Check if a diagram element belongs together with any other diagram element (using binary classification True/False)
belong_together = SegmentationClassification(configuration="yaml_config/belong_together.yaml", client=tclient)

''' PHASE 3 '''
# Task 2: Choose the diagram element which belongs together with the element from Task 1 (using the annotation tool "point")
choose_element = ImageSegmentation(configuration="yaml_config/choose_element.yaml", client=tclient)

''' PHASE 2 '''
''' Aggregate and Forward Actions needed to process outputs from Task 1 (Phase 1) '''

# Forward action that forwards all outputs in belong_together (Task 1) with output "True" to choose_element (Task 2, Phase 3)
forward_choose = Forward(configuration="yaml_config/forward_choose.yaml",
                         client=tclient,
                         targets=[choose_element])

# Aggregate action that aggregates outputs from belong_together (Task 1) using Dawid-Skene probabilistic model from Crowd-Kit library
aggregate_ds = Aggregate(configuration="yaml_config/aggregate_ds.yaml",
                         task=belong_together,
                         forward=forward_choose)

''' PHASE 4 '''
# Join elements: Group the chosen diagram element with the original highlighted element and
# forward those grouped elements to belong_together (Task 1, Phase 1) to reprocessed
join_boxes = JoinBBoxes(configuration="yaml_config/join_elements.yaml",
                        task=choose_element,
                        target=belong_together)


''' CONSTRUCT THE CROWDSOURCING PIPELINE WITH ALL TASKS, ACTIONS AND PROCESSES '''

# Add the task into a pipeline
pipe = TaskSequence(sequence=[belong_together,          # Phase 1. Toloker Task 1 (Does highlighted element/elements belong together with any other diagram element?)
                                                        # Phase 2.
                              aggregate_ds,                     # --> Aggregate outputs of belong_together using Dawid-Skene probabilistic model
                              forward_choose,                   # --> Forward outputs to choose_element (Phase 3)
                              choose_element,
                              join_boxes],              # Phase 3. Toloker Task 2 (Choose the element which belongs together with the highlighted element/elements.)
                                                        # Phase 4. Python code that joins the chosen elements together and forwards them back to belong_together (Phase 1)
                    client=tclient)


# Start the task sequence; create the tasks on Toloka
pipe.start()
