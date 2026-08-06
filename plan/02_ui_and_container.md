# Realisation Plan: UI and Container Runtime

## UI choice

Use a lightweight locally run web UI. Good candidates:

- **Streamlit**: fastest for MVP, easy progress display, easy file/path inputs
- **Gradio**: also viable, but slightly less natural for multi-step local workflow
- **Flask/FastAPI + custom frontend**: more flexible, slower to deliver

## Recommendation

Use **Streamlit** for MVP unless there is a strong reason to avoid it.

## UI requirements

### Inputs
- corpus directory path
- output directory path
- LM Studio base URL
- model name
- optional run settings:
  - max files for test run
  - enable/disable semantic relation inference
  - enable/disable preprocessing fallback mode

### Outputs shown in UI
- current stage
- current file count / total
- warnings
- final artifact paths
- download links where practical

## Progress model

Suggested stages:

1. validating inputs
2. starting container
3. preprocessing files
4. extracting entities
5. extracting relations
6. building graph
7. exporting artifacts
8. completed

## Container strategy

Use one fixed image and mount:

- input corpus dir: read-only if possible
- output dir: writable
- app code dir: mounted in development, baked into image in stable use

## Host-to-container LLM access

Because LM Studio runs on host:

- use OpenAI-compatible API
- configurable base URL from UI
- on Linux, ensure container can reach host:
  - `host.docker.internal` may need explicit support,
  - or pass host gateway via Docker run flags,
  - or use user-supplied reachable host address.

## Recommended runtime approach

For MVP:

- run Python app locally,
- trigger Dockerized pipeline execution as subprocess,
- poll logs/status files for progress,
- read artifacts from mounted output dir.

This is simpler than embedding UI inside container orchestration.

## Deliverables

- UI shell with form inputs
- run button
- progress area
- completion/result panel
- Docker command builder/executor
