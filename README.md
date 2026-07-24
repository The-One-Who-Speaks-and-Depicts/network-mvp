# Female Character Network Visualizer

Current status: early setup with local UI shell, Docker runner, LLM client wrapper, and file ingestion.

This repository currently contains:

- project description
- implementation plan
- repository scaffold
- Python dependency manifest
- runnable Docker image
- CI checks
- local Streamlit UI shell
- Docker runner wiring
- LLM client wrapper
- file ingestion and original-text logging
- normalization stage
- lemmatization stage
- candidate entity extraction
- entity merge logic
- co-occurrence edge generation
- semantic relation annotation
- graph construction and centrality
- graph JSON and HTML export
- progress reporting
- smoke and schema validation

It does **not yet** contain full text-processing pipeline. Current preprocessing, extraction, edge-generation, semantic-annotation, graph-construction, export, progress-reporting, and smoke/schema validation stages exist as service layers, but container entrypoint still runs scaffold output only.

## Version

Current development version: `0.17.0-dev`

## Requirements

To run locally, you need:

- Python 3.12
- Docker

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Optional later requirement:

- LM Studio in server mode, once LLM integration is implemented

## Repository layout

```text
app/         Python application package
logs/        exported logs
output/      exported artifacts
plan/        implementation plan and issue breakdown
prompts/     prompt templates
scripts/     helper scripts
tests/       test suite
```

## Configuration

Current code includes runtime configuration model in `app/config.py`.

Supported environment variables:

- `NETWORK_MVP_INPUT_DIR`
- `NETWORK_MVP_OUTPUT_DIR`
- `NETWORK_MVP_LMSTUDIO_BASE_URL`
- `NETWORK_MVP_MODEL_NAME`
- `NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION`
- `NETWORK_MVP_ENABLE_DEBUG_LOGGING`

Example:

```bash
export NETWORK_MVP_INPUT_DIR=./data
export NETWORK_MVP_OUTPUT_DIR=./output
export NETWORK_MVP_LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
export NETWORK_MVP_MODEL_NAME=local-model
export NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION=true
export NETWORK_MVP_ENABLE_DEBUG_LOGGING=false
```

Note: current scaffold entrypoint does not consume these values yet. Config model and loaders are ready for next integration steps.

## LLM client

Current code includes OpenAI-compatible wrapper in `app/services/llm_client.py`.

Current wrapper supports:

- base URL from config
- model name from config
- timeout setting
- prompt request helper
- response text extraction
- actionable error messages for request/response failures

Intended target:

- LM Studio in OpenAI-compatible server mode

## Local Python run

From repository root:

```bash
python3 -m app.main
```

Expected output:

```text
Female Character Network Visualizer scaffold
Start local UI with: streamlit run app/ui/app.py
```

## Local UI run

From repository root:

```bash
streamlit run app/ui/app.py
```

Current UI provides:

- corpus directory field
- output directory field
- LM Studio base URL field
- model name field
- Start run button
- status area with container stdout/stderr
- current stage display
- file-count progress display where backend reports counts
- clear completion/failure state

## File ingestion

Current code includes file ingestion service in `app/pipeline/file_ingestion.py`.

Current service supports:

- recursive `.txt` discovery
- stable file IDs
- per-file UTF-8 loading
- filename provenance retention
- original-text export to `output/logs/original/`

## Normalization

Current code includes normalization service in `app/pipeline/normalization.py`.

Current service supports:

- prompt template in `prompts/normalization_prompt.txt`
- per-file normalization requests via LLM client
- line-break removal in normalized output
- per-file writes to `output/normalized/`
- malformed or empty-output logs in `output/logs/normalization/`

## Lemmatization

Current code includes lemmatization service in `app/pipeline/lemmatization.py`.

Current service supports:

- prompt template in `prompts/lemmatization_prompt.txt`
- per-file lemma-sequence requests via LLM client
- per-file writes to `output/lemmas/`
- malformed or empty-output logs in `output/logs/lemmatization/`

## Candidate entity extraction

Current code includes candidate entity extraction service in `app/pipeline/entities.py`.

Current service supports:

- prompt template in `prompts/entity_extraction_prompt.txt`
- per-file candidate extraction via LLM client
- candidate record format with:
  - file ID
  - filename
  - candidate name
  - evidence text
- direct-name-first parsing from tab-separated LLM output

## Entity merge logic

Current code includes entity merge service in `app/pipeline/entity_merge.py`.

Current service supports:

- canonical entity record generation
- alias grouping
- source-file aggregation
- evidence aggregation
- basic title stripping for canonicalization
- basic `gender_inference` population

## Co-occurrence edge generation

Current code includes co-occurrence service in `app/pipeline/cooccurrence.py`.

Current service supports:

- file-level co-occurrence grouping
- unique pair generation
- weighted edge aggregation
- source-file tracking per edge
- self-loop avoidance through unique pair combinations

## Semantic relation annotation

Current code includes semantic relation service in `app/pipeline/semantic_relations.py`.

Current service supports:

- prompt template in `prompts/semantic_relation_prompt.txt`
- optional enable/disable behavior
- allowed-label mapping to project schema
- confidence parsing
- `not stated` fallback on unknown labels or request failures

## Graph construction and centrality

Current code includes graph builder in `app/graph/build.py`.

Current service supports:

- NetworkX graph construction from canonical entities and semantic edges
- node/edge attribute mapping
- eigenvector centrality computation
- warning capture for empty or problematic graphs
- centrality write-back onto node attributes

## Graph export

Current code includes graph exporter in `app/graph/export.py`.

Current service supports:

- `graph.json` export with node and edge records
- node centrality in JSON output
- node and edge source references in JSON output
- static HTML artifact export
- pyvis-backed HTML when dependency is available
- fallback static HTML artifact when pyvis is unavailable

## Progress reporting

Current code includes progress reporting model in `app/progress/reporting.py`.

Current service supports:

- parsing backend progress lines from container stdout
- current stage extraction
- file-count progress extraction where reported
- completion/failure state derivation
- UI display of stage, counts, and final state

Progress line format:

```text
PROGRESS\tstage=<stage>\tcompleted=<n>\ttotal=<n>\tstatus=<state>\tmessage=<text>
```

## Smoke and schema validation

Current test suite now includes:

- config default/validation coverage
- `graph.json` shape validation
- tiny-corpus happy-path smoke coverage
- artifact generation checks for JSON and HTML outputs

Smoke flow covers:

- ingestion
- normalization
- lemmatization
- entity extraction
- entity merge
- co-occurrence generation
- semantic annotation
- graph build
- graph export

## Local test run

Run compile check:

```bash
python3 -m compileall app tests scripts
```

Run tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## Docker run

Build image:

```bash
docker build -t network-mvp:test .
```

Run container:

```bash
docker run --rm network-mvp:test
```

Expected output:

```text
Female Character Network Visualizer scaffold
Start local UI with: streamlit run app/ui/app.py
UI launches Docker container for pipeline runs
```

## Docker runner behavior

Current Docker runner mounts:

- input directory to `/data/input`
- output directory to `/data/output`

Current Docker runner passes environment variables into container:

- `NETWORK_MVP_INPUT_DIR=/data/input`
- `NETWORK_MVP_OUTPUT_DIR=/data/output`
- `NETWORK_MVP_LMSTUDIO_BASE_URL=...`
- `NETWORK_MVP_MODEL_NAME=...`
- `NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION=...`
- `NETWORK_MVP_ENABLE_DEBUG_LOGGING=...`

## Docker permissions note

If Docker is installed but you get a permission error for `/var/run/docker.sock`, either:

```bash
newgrp docker
```

or log out and log back in, then retry.

Temporary workaround for current shell:

```bash
sg docker -c 'docker run --rm network-mvp:test'
```

## CI checks

Current GitHub Actions pipeline checks:

- Python source compiles
- tests pass
- no tracked Python cache artifacts
- Docker image builds
- Docker container entrypoint runs
- PRs into `dev` update `VERSION`
- PRs into `dev` update `plan/issue_status.md`
- PRs into `dev` mark at least one issue as completed

## Next expected capabilities

Planned future steps:

- documentation and runbook

## Main project document

See:

- `project_description.md`
