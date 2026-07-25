# Female Character Network Visualizer

## Stack

* Main language: Python
* Required packages: NetworkX, pyvis, pandas
* Additional tools: Docker, local LLM
* Runtime constraints: I have no ability to train or fine-tune models, only to run a model smaller than 4GB.

## Workflow

* Run a GUI interface (a locally run web UI)
* Accept the data location
* Accept the local LLM configuration (I will be using LM Studio)
* Initialise a Docker container for each run (use a fixed image and mount code/data volumes into the container); ensure that the container has access to a local LLM (LM Studio in server mode on localhost, via an OpenAI-compatible API)
* Preprocess the data
* Run the pipeline
* Get the output
* Export the output artifact from the container back to the host
* Show progress in the GUI

## Data

* Corpus size: no more than 50K tokens
* Number of texts: approx. 1000; only a couple are longer than two lines (most are birchbark letters)
* Raw texts, each in a separate `.txt` file
* File size: very small, usually no more than 1 KB

## Preprocessing steps

* Perform preprocessing for each file
* Normalisation: convert the data to canonical Old East Slavic form, restoring etymological reduced vowels, yats, and `в/у`. Delete line breaks. Preserve punctuation. Preserve token count alignment where possible (approximate alignment is acceptable). Store the original in a log (per file, inside the container, plain text; export it outside the container after the run). Expected output: the same text, but normalised.
* Lemmatisation: produce a plain-text lemma sequence for each file
* Use a local LLM for both steps; if possible, a Russian National Corpus-based dictionary and rule-based system will also suffice

## Pipeline

* Extract all named characters; merge aliases/nicknames, historical titles, and patronymics; use a maximally aggressive merge strategy; include pronoun/coreference handling; allow group entities; define a character mention as a direct mention of a name or a very confidently traceable anaphoric reference
* Extract the relationships between them (co-occurrence in the same fragment, at text/file level); attempt to infer semantic relations and their directions with a local LLM; use weighted edges, where `edge.weight` = number of files in which 2 entities co-occur
* Semantic relations: princess of Y, wife of X, daughter of X, mother of X, sister of X, grandmother of X, aunt of X, granddaughter of X, in-law of X, prince of Y, husband of X, son of X, father of X, brother of X, grandfather of X, uncle of X, grandson of X, not stated (if a relation does not fit the schema, mark it as `not stated`; it will be eliminated in manual post-processing, and the schema will be corrected afterwards if necessary; this is a human-in-the-loop step). Add a confidence score.
* Visualise the relationships between them in graph form (use eigenvector centrality)
* Highlight female characters (infer from names; allow ambiguous cases; assume the data renders gender correctly, but include a disclaimer about this)
* Tagging schema: `gender_inference: female|ambiguous|unresolved|not-inferred`
* Keep all nodes
* Use `gender_inference` for all nodes
* Visually highlight only female nodes
* Label each node with the canonical actor name; female labels should be visually marked with surrounding underscores
* Put detailed node and edge metadata into hover pop-ups rather than crowding the graph canvas
* Provide a control in the HTML artifact to hide/show all non-female nodes while preserving them in the underlying graph

## Artifact

* HTML network graph that can be loaded on a static web page (Codeberg Pages / GitHub Pages); data format should match that requirement
* `graph.html` should be a self-contained demo page, not only a raw graph canvas: include a short explanation of the demo and embed the project description text
* Graph for the whole corpus; retain file/source references as lists of file names (not full paths)
* Include the source texts used by the exported graph in the HTML page, limited to files referenced by graph nodes or edges
* Allow downloading nodes/edges as JSON (`graph.json`: nodes + edges, centrality embedded in nodes, source references on both nodes and edges, semantic relation confidence attached to edges)
* One edge can contain both weight and optional semantic annotation
* Character centralities
* Gender inference tags
* Obtainable outside the container
