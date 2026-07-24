# Issue 19: Lemmatized pipeline alignment and quality gates

## Scope

Align entity and relation extraction with lemmatized-text pipeline expectations, add static quality gates, and update docs to match plan and project description.

## Deliverables

- entity extraction driven by lemmatized text
- semantic relation annotation driven by lemmatized context
- source-text support retained where evidence or provenance needs it
- `pylint` and `mypy` added to dependencies and CI
- documentation updated for pipeline behavior, validation, and operator workflow

## Acceptance criteria

- smoke flow extracts entities from lemmatized outputs
- semantic annotation consumes lemmatized context in tests
- CI runs `pylint` and `mypy`
- docs describe current pipeline behavior and manual cleanup expectations
