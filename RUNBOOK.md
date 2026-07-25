# Runbook

## Goal

Run local UI, validate local environment, inspect scaffolded pipeline outputs, and handle manual cleanup.

## Prerequisites

- Python 3.12
- Docker
- Python dependencies from `requirements.txt`
- optional: LM Studio in server mode for local LLM-backed stages

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## LM Studio setup

Recommended local setup:

- open LM Studio
- load small model that fits local hardware limits
- enable server mode
- confirm endpoint `http://127.0.0.1:1234/v1`
- copy exact model name into UI form

If using different host or port, update UI form or environment variables.

## Input corpus

Expected corpus:

- `.txt` files
- UTF-8
- one text per file
- filenames retained as provenance in outputs

Tiny sample corpus layout:

```text
sample-data/
├── 003.003.txt
└── 004.004.txt
```

## Start UI

```bash
streamlit run app/ui/app.py
```

Fill:

- corpus directory
- output directory
- LM Studio base URL
- model name

Press `Start run`.

## Pipeline notes

Current service-layer pipeline order:

1. ingestion
2. normalization
3. lemmatization
4. entity extraction from lemmatized text, with source text retained for evidence snippets
5. entity merge
6. co-occurrence edge build
7. semantic relation annotation from lemmatized context, with source text retained as supporting evidence
8. graph build
9. graph export

Current container entrypoint remains scaffold-oriented. Full orchestration still partial.

## Watch progress

UI currently shows:

- current stage
- file counts when backend reports them
- completion or failure state
- container stdout/stderr

Current backend emits scaffold progress contract lines like:

```text
PROGRESS	stage=startup	completed=0	total=0	status=running	message=Container started
```

## Outputs

Inspect:

- `output/logs/original/`
- `output/normalized/`
- `output/lemmas/`
- `output/graph.json`
- `output/graph.html`

Check:

- `graph.json` contains `nodes` and `edges`
- node records include `centrality_eigenvector`
- nodes and edges keep `source_files`
- `graph.html` opens as static file
- graph page shows explanatory text and project description
- node labels show canonical actor names
- female labels are wrapped in underscores
- node and edge details appear on hover
- hide/show non-female control works
- source-text appendix lists files referenced by graph nodes and edges

## Manual post-processing

Human review required.

Review exported graph for:

- `semantic_relation = "not stated"`
- low-confidence semantic labels
- over-merged entities
- conservative `gender_inference`
- suspicious provenance on `source_files`
- misleading female/non-female highlighting
- labels or pop-ups that confuse readers
- source texts that should not appear or are missing from appendix

Manual cleanup steps:

1. remove or relabel `not stated` edges
2. inspect low-confidence semantic labels
3. keep source-file evidence intact
4. revise downstream schema if repeated valid relation falls outside allowed labels

## Known limits

Current repo still scaffold-first.

Limits:

- container entrypoint not wired to full end-to-end runtime pipeline yet
- UI triggers Docker run, not full artifact-rich production workflow
- progress updates depend on parseable stdout lines
- semantic relation labels constrained to fixed schema
- `not stated` output expected; human cleanup required
- gender inference heuristic coarse, name-based, conservative
- graph export works from service layer and tests; full container orchestration still pending integration

## Troubleshooting

### Docker socket permission error

Use:

```bash
newgrp docker
```

Or temporary workaround:

```bash
sg docker -c 'docker run --rm network-mvp:test'
```

### Missing Python package tools

If `pip` unavailable, install system package support for `pip` / `venv` first, then rerun:

```bash
python3 -m pip install -r requirements.txt
```

### Empty or missing stage outputs

Check:

- `output/logs/normalization/`
- `output/logs/lemmatization/`
- UI stderr block
- container stdout progress lines

## Lint and type checks

Run:

```bash
python3 -m pylint app tests scripts
python3 -m mypy app tests scripts
```

## Validation

```bash
python3 -m compileall app tests scripts
python3 -m unittest discover -s tests -p 'test_*.py' -v
GITHUB_BASE_REF=dev python3 scripts/check_pr_requirements.py
```
