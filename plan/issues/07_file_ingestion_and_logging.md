# Issue 07: File ingestion and original-text logging

## Scope

Implement `.txt` discovery, per-file loading, stable file IDs, and export of original texts to logs.

## Deliverables

- file discovery function
- per-file loader
- original-text writer to `logs/original/`

## Acceptance criteria

- only `.txt` files are processed
- filenames are retained for provenance
- original text logs are exported outside container
