# Realisation Plan: Entities and Relations

## Entity extraction goals

Detect named characters across the corpus and consolidate them into canonical nodes.

## Entity pipeline

1. extract candidate named characters per file
2. capture mention spans or text snippets where practical
3. infer canonical forms
4. merge aliases/nicknames
5. merge historical titles
6. merge patronymics
7. optionally merge group entities
8. attach provenance

## Merge policy

Use a **maximally aggressive merge strategy**, but keep enough trace data to audit merges later.

Suggested node fields:

- `id`
- `label`
- `aliases`
- `titles`
- `patronymics`
- `entity_type` (`person` or `group`)
- `gender_inference`
- `source_files`
- `mention_count`

## Coreference policy

Only accept direct names or very confidently traceable anaphoric references.

## Relation extraction goals

### Baseline relation
- co-occurrence within same file
- undirected graph topology
- edge weight = number of files in which 2 entities co-occur

### Optional semantic annotation
Attempt semantic relation extraction with direction and confidence.

Suggested edge fields:

- `source`
- `target`
- `weight`
- `source_files`
- `semantic_relation`
- `semantic_direction`
- `semantic_confidence`

## Supported semantic labels

- princess of
- wife of
- daughter of
- mother of
- sister of
- grandmother of
- aunt of
- granddaughter of
- in-law of
- prince of
- husband of
- son of
- father of
- brother of
- grandfather of
- uncle of
- grandson of
- not stated

## Human-in-the-loop step

If extracted relation does not fit schema:

- mark as `not stated`
- keep for review if useful during inspection
- remove during manual post-processing
- optionally revise schema after inspection

## Deliverables

- entity extraction module
- merge rules module
- relation extraction module
- semantic annotation prompt(s)
- provenance-aware node/edge records
