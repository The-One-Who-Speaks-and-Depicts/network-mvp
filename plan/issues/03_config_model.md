# Issue 03: Configuration model

## Scope

Define runtime configuration structure for paths, LM Studio settings, and feature toggles.

## Deliverables

- config dataclass or equivalent in `app/config.py`
- config loader from UI inputs and/or env vars

## Acceptance criteria

- config object includes input dir, output dir, base URL, model name
- optional flags supported for semantic annotation and debug logging
- invalid/missing required fields surface clear errors
