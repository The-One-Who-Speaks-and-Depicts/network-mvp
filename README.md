# Female Character Network Visualizer

Current status: scaffold / early setup.

This repository currently contains:

- project description
- implementation plan
- repository scaffold
- Python dependency manifest
- runnable Docker image
- CI checks

It does **not yet** contain the actual text-processing pipeline or web UI. The current app entrypoint only prints a scaffold message.

## Version

Current development version: `0.2.0-dev`

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

## Local Python run

From repository root:

```bash
python3 -m app.main
```

Expected output:

```text
Female Character Network Visualizer scaffold
```

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
```

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

- config model
- local web UI
- Docker runner integration
- LM Studio client
- preprocessing pipeline
- graph generation and export

## Main project document

See:

- `project_description.md`
