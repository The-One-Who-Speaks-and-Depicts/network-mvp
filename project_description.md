# Female Character Network Visualizer

## Project Summary

This project builds a local research demo for exploring character networks in Old East Slavic texts, with a special focus on women mentioned in the corpus. The application processes a directory of short `.txt` files, runs a lightweight NLP pipeline with a local LLM, extracts named characters and their relationships, and exports an interactive graph together with machine-readable artifacts.

The goal is not to produce a final scholarly edition automatically. The goal is to produce a transparent, inspectable demo that helps a researcher move from a raw corpus to a graph that can be reviewed, corrected, and discussed.

## Technical Constraints

- Main language: Python
- Core packages: NetworkX, pyvis, pandas
- Runtime environment: local machine with Docker
- LLM runtime: local OpenAI-compatible endpoint, expected to be LM Studio
- Model constraint: no fine-tuning; model size should remain below roughly 4 GB

## User Workflow

The intended workflow is:

1. launch a local web UI,
2. choose the corpus directory,
3. provide local LLM settings,
4. start a Dockerized run,
5. preprocess the corpus,
6. extract characters and relations,
7. build the corpus-wide graph,
8. export artifacts back to the host machine,
9. inspect results in the browser and in exported files.

The UI should also surface progress and fail clearly when the pipeline cannot continue.

## Corpus Assumptions

- Corpus size: up to roughly 50K tokens
- Number of texts: about 1000
- Typical file size: very small, often under 1 KB
- File format: one raw `.txt` file per text
- Text profile: mostly very short birchbark letters, with only a few longer texts

## Preprocessing

Each file should pass through two preprocessing steps:

### 1. Normalization

Normalize the text into a canonical Old East Slavic form.

Requirements:

- restore etymological reduced vowels where possible,
- restore yats where possible,
- normalize `в/у`,
- remove line breaks,
- preserve punctuation,
- preserve approximate token alignment where possible.

The original text must also be stored in a per-file log and exported outside the container.

### 2. Lemmatization

Produce a plain-text lemma sequence for each file.

Both normalization and lemmatization are expected to use a local LLM, although a rule-based or dictionary-supported fallback would also be acceptable if introduced later.

## Entity and Relation Extraction

The pipeline should:

- extract named characters,
- merge aliases, nicknames, titles, and patronymics aggressively,
- support very confident anaphoric/coreferential references,
- allow group entities where appropriate,
- define a character mention as a direct name mention or a very confidently traceable anaphoric reference,
- delegate gender inference for merged entities to the local LLM rather than relying primarily on suffix rules.

Relations should be built primarily from co-occurrence within the same file or fragment. Edge weights should equal the number of files in which two entities co-occur.

The system should also attempt optional semantic relation annotation with a local LLM.

Allowed semantic labels:

- princess of Y
- wife of X
- daughter of X
- mother of X
- sister of X
- grandmother of X
- aunt of X
- granddaughter of X
- in-law of X
- prince of Y
- husband of X
- son of X
- father of X
- brother of X
- grandfather of X
- uncle of X
- grandson of X
- not stated

If a relation does not fit the schema, it should be marked as `not stated`. This is an expected human-in-the-loop outcome, not a hard error.

## Graph Requirements

The final graph should represent the whole corpus and compute eigenvector centrality for nodes.

Node requirements:

- keep all nodes in the graph,
- assign `gender_inference` to all nodes,
- infer `gender_inference` from merged aliases and evidence with the local LLM as the primary method,
- use the canonical actor name as the displayed node label,
- wrap female labels in underscores for visual emphasis,
- keep detailed metadata out of the main label and move it into hover pop-ups.

Gender tagging schema:

- `female`
- `ambiguous`
- `unresolved`
- `not-inferred`

The graph should visually highlight only female nodes, while preserving all other nodes for context. The HTML artifact should also provide a control to hide or show non-female nodes without deleting them from the graph.

## Exported Artifacts

The project should export artifacts that can be opened directly outside the container.

### `graph.html`

`graph.html` should be a self-contained static demo page suitable for static hosting.

It should include:

- an explanation of what the graph shows,
- a polished project description,
- an interactive network view,
- hover pop-ups for node and edge metadata,
- a control to hide/show non-female nodes,
- the source texts used in the exported graph,
- a raw graph-data section for inspection.

### `graph.json`

`graph.json` should contain:

- nodes,
- edges,
- centrality embedded in node records,
- source-file references on both nodes and edges,
- semantic relation confidence on edges where available.

### Additional expectations

- one edge may contain both a co-occurrence weight and a semantic annotation,
- file references should use file names, not full paths,
- artifacts should remain inspectable and easy to review manually.

## Research and Interpretation Notes

This project is meant as a research aid, not as a fully automatic truth-producing system.

Important caveats:

- gender inference is now delegated to the local LLM, but still remains heuristic and reviewable rather than definitive,
- normalization and lemmatization may be imperfect,
- entity merging may occasionally be too aggressive, especially when extraction noise pollutes a candidate string,
- semantic relation labels may require manual correction,
- `not stated` is an expected and acceptable intermediate label.

The system should therefore prioritize transparency, provenance, and manual reviewability over false precision.
