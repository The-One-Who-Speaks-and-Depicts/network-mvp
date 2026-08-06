# Realisation Plan: Graph and Artifacts

## Graph construction

Use NetworkX as primary graph engine.

## Graph model

### Nodes
Required attributes:

- `id`
- `label` (canonical actor name; wrap in underscores for `female` nodes in HTML/JSON export)
- `canonical_name`
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

Use static-hostable HTML with client-side graph interactivity.

### Visual rules
- highlight `female` nodes distinctly
- keep all other nodes visible by default
- show canonical actor name directly on node label
- wrap female node labels in underscores
- move detailed node metadata into hover pop-ups:
  - canonical name
  - gender inference
  - aliases
  - evidence
  - centrality
  - source files
- show edge weight
- show semantic relation/confidence/source files in edge pop-ups
- provide UI control to hide/show all non-female nodes
- include explanatory text around graph so artifact reads as a demo page, not only a canvas

## JSON export

Create `graph.json` with:

- `nodes`: node objects
- `edges`: edge objects
- node labels aligned with HTML labels
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
- can be served from GitHub Pages / Codeberg Pages,
- includes project-description copy,
- includes source-text appendix limited to files used in graph.

## Deliverables

- graph builder
- centrality calculator
- HTML demo-page exporter
- JSON exporter
- optional CSV exporters
