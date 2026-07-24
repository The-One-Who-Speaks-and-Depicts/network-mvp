# Realisation Plan: Overview

## Goal

Build a local, Docker-run Python application that:

1. accepts a directory of `.txt` files,
2. preprocesses Old East Slavic texts,
3. extracts named characters and relations,
4. builds a whole-corpus character graph,
5. highlights female characters,
6. exports a static HTML graph plus JSON artifacts.

## Delivery strategy

Implementation should be phased to reduce risk from local-model quality and historical-language ambiguity.

## Phases

1. **Project skeleton**
   - repository structure
   - Python package/app entrypoints
   - Docker image
   - local web UI shell
2. **Container + LM Studio integration**
   - host/container API connectivity
   - model configuration input
   - prompt execution wrapper
3. **Preprocessing pipeline**
   - file discovery
   - normalization
   - lemmatization
   - original-text logging/export
4. **Entity and relation extraction**
   - character extraction
   - merge strategy
   - co-occurrence edges
   - optional semantic relation annotation
5. **Graph construction + artifacts**
   - NetworkX graph build
   - eigenvector centrality
   - `graph.json`
   - HTML visualization
6. **UX + hardening**
   - progress reporting
   - error surfacing
   - manual post-processing support
   - validation on sample corpus

## MVP definition

MVP should prioritize:

- successful local run from web UI,
- Docker execution,
- LM Studio connectivity,
- whole-corpus graph generation,
- female-node highlighting,
- `graph.json` + HTML export.

Semantic relation quality can be iterative after MVP.

## Key risks

- small local model quality for Old East Slavic normalization,
- over-aggressive entity merging,
- noisy coreference,
- sparse or misleading co-occurrence graph,
- semantic relations requiring manual cleanup.

## Acceptance criteria

A run is successful when it:

- processes all input `.txt` files,
- exports original-text logs,
- produces normalized and lemmatized outputs,
- builds graph with weighted edges,
- calculates eigenvector centrality,
- writes static HTML graph and `graph.json` outside container,
- shows run progress in UI.
