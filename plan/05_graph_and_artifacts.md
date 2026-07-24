# Realisation Plan: Graph and Artifacts

## Graph construction

Use NetworkX as primary graph engine.

## Graph model

### Nodes
Required attributes:

- `id`
- `label`
- `gender_inference`
- `centrality_eigenvector`
- `source_files`
- optional alias metadata

### Edges
Required attributes:

- `source`
- `target`
- `weight`
- `source_files`
- optional semantic annotation
- optional semantic confidence

## Centrality

Primary metric:

- eigenvector centrality

Implementation notes:

- handle disconnected graphs gracefully,
- log failures or fallback handling if computation becomes unstable.

## HTML visualization

Use pyvis to export static-hostable HTML.

### Visual rules
- highlight `female` nodes distinctly
- keep all other nodes visible
- show tooltip metadata:
  - label
  - gender inference
  - centrality
  - source file count
- show edge weight
- show semantic relation/confidence if present

## JSON export

Create `graph.json` with:

- `nodes`: node objects
- `edges`: edge objects
- optional metadata block:
  - run timestamp
  - model name
  - corpus stats

## Additional exports

Recommended:

- `centralities.csv`
- `nodes.csv`
- `edges.csv`
- `run_summary.json`

## Static hosting compatibility

Ensure HTML artifact:

- opens without server-side rendering,
- uses portable asset references,
- can be served from GitHub Pages / Codeberg Pages.

## Deliverables

- graph builder
- centrality calculator
- pyvis exporter
- JSON exporter
- optional CSV exporters
