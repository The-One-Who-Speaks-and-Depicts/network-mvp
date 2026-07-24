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

It does **not yet** contain full text-processing pipeline. Current normalization stage exists as service layer, but container entrypoint still runs scaffold output only.

## Version

Current development version: `0.8.0-dev`

## Requirements

To run locally, you need:

- Python 3.12
- Docker

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

- remaining preprocessing stages
- graph generation and export

## Main project document

See:

- `project_description.md`
