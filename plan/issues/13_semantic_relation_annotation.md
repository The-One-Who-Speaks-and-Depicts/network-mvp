# Issue 13: Semantic relation annotation

## Scope

Add optional semantic relation labels, direction, and confidence to existing edges.

## Deliverables

- semantic relation prompt
- label mapping to allowed schema
- confidence field
- `not stated` handling

## Acceptance criteria

- semantic annotation can be toggled on/off
- only schema-approved labels or `not stated` are emitted
- confidence stored on edge record
