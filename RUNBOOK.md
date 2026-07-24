# Runbook

## Goal

Run local UI, execute current scaffolded pipeline flow, inspect artifacts, handle manual cleanup.

## Prerequisites

- Python 3.12
- Docker
- Python dependencies from `requirements.txt`
- optional: LM Studio in server mode for stages that call local LLM

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## 1. Start LM Studio

Needed once full pipeline wiring consumes live model calls.

Recommended local setup:

- Open LM Studio
- Load small local model that fits machine constraints
- Start server mode
- Confirm OpenAI-compatible endpoint available at `http://127.0.0.1:1234/v1`
- Copy exact model name shown by LM Studio

If using different host or port, update UI form or environment variables.

## 2. Prepare corpus

Input expectations:

- plain `.txt` files
- one text per file
- UTF-8 encoding
- filenames kept as provenance in output artifacts

Tiny sample corpus layout:

```text
sample-data/
├── 003.003.txt
└── 004.004.txt
```

## 3. Start UI

```bash
streamlit run app/ui/app.py
```

Fill:

- Corpus directory
- Output directory
- LM Studio base URL
- Model name

Press `Start run`.

## 4. Watch progress

UI currently shows:

- current stage
- file counts when backend reports them
- completion or failure state
- container stdout/stderr

Current backend emits scaffold progress contract lines like:

```text
PROGRESS	stage=startup	completed=0	total=0	status=running	message=Container started
```

## 5. Inspect outputs

Current codebase exports or prepares:

- `output/logs/original/`
- `output/normalized/`
- `output/lemmas/`
- `output/graph.json`
- `output/graph.html`

Key artifact checks:

- `graph.json` has `nodes` and `edges`
- node records include `centrality_eigenvector`
- node and edge records include `source_files`
- `graph.html` opens as static file in browser

## 6. Manual post-processing

Human review still required.

Review `graph.json` edges for:

- `semantic_relation = "not stated"`
- weak semantic confidence
- over-merged entities
- unresolved gender inference
- suspicious source-file provenance

Manual cleanup expectations:

1. remove or relabel `not stated` edges as research needs dictate
2. inspect low-confidence semantic labels
3. correct schema if repeated relation type falls outside allowed label set
4. preserve source-file evidence during manual edits

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

## Validation commands

```bash
python3 -m compileall app tests scripts
python3 -m unittest discover -s tests -p 'test_*.py' -v
GITHUB_BASE_REF=dev python3 scripts/check_pr_requirements.py
```
