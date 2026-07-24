# Issue 05: Docker runner

## Scope

Implement code that launches pipeline container with mounted input/output paths and LLM connectivity settings.

## Deliverables

- Docker command builder
- subprocess runner
- captured stdout/stderr log handling

## Acceptance criteria

- app can launch container from local UI/backend layer
- mounts for input/output are correct
- base URL/model settings are passed into runtime
