# Realisation Plan: Architecture

## Proposed repository structure

```text
.
├── project_description.md
├── plan/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── models/
│   ├── services/
│   ├── pipeline/
│   ├── graph/
│   ├── ui/
│   └── main.py
├── prompts/
├── scripts/
├── output/
├── logs/
├── tests/
├── Dockerfile
├── docker-compose.yml        # optional, only if useful for local orchestration
├── requirements.txt
└── README.md
```

## Main modules

### `app/config.py`
- runtime configuration
- paths
- LM Studio API settings
- output locations

### `app/services/llm_client.py`
- OpenAI-compatible client wrapper
- model selection
- prompt sending
- retries/timeouts
- response normalization

### `app/pipeline/preprocess.py`
- file loading
- normalization
- lemmatization
- original logging

### `app/pipeline/entities.py`
- character extraction
- alias/title/patronymic merge rules
- confidence handling

### `app/pipeline/relations.py`
- file-level co-occurrence edges
- optional semantic relation inference
- semantic relation confidence

### `app/graph/build.py`
- NetworkX graph creation
- node/edge attributes
- weight aggregation
- centrality computation

### `app/graph/export.py`
- `graph.json`
- centrality tables
- auxiliary outputs

### `app/ui/`
- local web UI
- form for input dir + LM Studio settings
- progress/status display
- download links for artifacts

## Data flow

1. user starts local web UI
2. user chooses input dir + LLM settings
3. app launches Docker run with mounted dirs
4. pipeline reads files
5. preprocessing outputs normalized text + lemma sequence + original logs
6. entity extraction creates canonical node candidates
7. relation extraction creates weighted co-occurrence edges
8. semantic annotation enriches eligible edges
9. graph builder computes centrality
10. exporters write HTML + JSON + logs outside container
11. UI displays completion + artifact locations

## Interface boundaries

### Inputs
- input directory path
- LM Studio base URL
- model name
- output directory

### Outputs
- HTML graph
- `graph.json`
- preprocessing logs
- optional CSV/TSV summaries

## Design principles

- deterministic pipeline stages where possible
- LLM isolated behind one client layer
- artifacts serializable and inspectable
- manual post-processing possible without rerunning entire pipeline
- keep source provenance on graph objects
