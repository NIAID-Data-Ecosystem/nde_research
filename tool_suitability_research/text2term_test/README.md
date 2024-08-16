## Purpose
To test the suitability of Text2Term for ontology mapping.

## Background
PubTator has been found to be an excellent tool for ontology mapping for taxonomic terms; however, the PubTator raw text processing API cannot handle the volume of processing needed by our project. For this reason, a suitable replacement is necessary

## Methods
Test performance on mapping alone: Pull all raw text taxonomic information from the `species` field in the records in the Discovery Portal and process them using Text2Term. Compare the results with previous results from PubTator.

Test performance on mapping EXTRACT processed terms: Run Text2Term on taxonomy terms identified by EXTRACT

Identify sources of weakness / error:
* Check if capitalization, character length affect Text2Term result quality
* Check Text2Term mapping against locations