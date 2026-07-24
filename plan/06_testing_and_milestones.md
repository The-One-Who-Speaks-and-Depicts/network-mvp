# Realisation Plan: Testing and Milestones

## Testing strategy

### Unit tests
Cover:

- file discovery
- config parsing
- prompt formatting
- merge rules
- graph assembly
- export schema validation

### Integration tests
Cover:

- end-to-end run on miniature corpus
- Docker invocation
- LM Studio client against mocked OpenAI-compatible endpoint
- artifact generation

### Manual validation
Because extraction quality is domain-sensitive, include manual checks for:

- normalization plausibility
- lemmatization plausibility
- merge correctness
- semantic relation correctness
- female highlighting correctness

## Suggested milestones

### Milestone 1: skeleton
- repo structure
- dependencies
- Dockerfile
- UI scaffold
- config layer

### Milestone 2: runnable pipeline shell
- input selection
- Docker run wiring
- progress reporting
- output directory wiring

### Milestone 3: preprocessing
- normalization
- lemmatization
- original logging
- summary reporting

### Milestone 4: graph core
- entity extraction
- file-level co-occurrence
- weighted edges
- NetworkX graph build

### Milestone 5: semantic enrichment
- semantic relation prompt
- confidence handling
- `not stated` workflow

### Milestone 6: visualization + exports
- pyvis HTML
- `graph.json`
- CSV summaries
- static-hosting validation

### Milestone 7: corpus validation
- run on representative subset
- inspect errors
- tune prompts/rules
- document limitations

## Definition of done

Project is done when:

- UI can launch full run locally,
- Dockerized pipeline completes successfully,
- artifacts are exported to host,
- graph is viewable as static HTML,
- `graph.json` is valid and complete,
- documentation explains workflow and limitations.
