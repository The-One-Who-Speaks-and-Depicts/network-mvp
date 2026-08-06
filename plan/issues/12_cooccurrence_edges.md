# Issue 12: Co-occurrence edge generation

## Scope

Build weighted graph edges from file-level co-occurrence.

## Deliverables

- pair-generation logic
- edge aggregation logic
- source-file tracking on edges

## Acceptance criteria

- each edge weight equals number of files where pair co-occurs
- self-loops avoided unless explicitly intended
- edge records serializable for graph build step
