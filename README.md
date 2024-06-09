# Crowdsourcing Compositionality

This repository contains the codebase used for the crowdsourcing experiment in my Bachelor's thesis *Crowdsourcing Descriptions of Compositionality in Multimodal Diagrams*.

The thesis focuses on constructing and testing a crowdsourcing pipeline aiming to see if annotations for compositionality in diagrams can be generated through crowdsourcing.

The thesis experiment was conducted using a University of Helsinki based command line tool *abulafia* [(Hiippala et al., 2022)](https://aclanthology.org/2022.latechclfl-1.2/ "Developing a tool for fair and reproducible use of paid crowdsourcing in the digital humanities") that works with [Toloka crowdsourcing platform](https://toloka.ai/). Thus, most of the code used in this experiment was written by modifying and reconstructing already existing code and using scripts or tools found at https://github.com/thiippal/abulafia and https://github.com/thiippal/toloka_tools.

The data used in the study is a sample set taken from the multimodal diagram dataset AI2D-RST [(Hiippala et al., 2021)](https://doi.org/10.1007/s10579-020-09517-1 "AI2D-RST: a multimodal corpus of 1000 primary school science diagrams"). The AI2D-RST dataset and related resources can be found at http://urn.fi/urn:nbn:fi:lb-2020060101 and https://github.com/thiippal/AI2D-RST.


### Codebase:

`pipeline_for_compositionality.png`: visualization of the pipeline as a whole

`pipeline_compositionality.py`: a pipeline used for creating the crowdsourcing tasks on Toloka

`yaml_config/`: contains YAML configuration files used for creating task objects and actions needed in the pipeline

`instructions/`: contains HTML files used for constructing and visualizing the instructions for the crowdsourcing tasks

`sample_dataset.tsv`: the sample dataset of 100 science-related diagrams used in the experiment

`custom_processor.py`: an additional new component which was needed to enable joining diagram elements together (this component and the "Join Elements" phase was built and implemented to the pipeline by my supervisor Dr. Tuomo Hiippala)