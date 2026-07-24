# Issue 06: LLM client wrapper

## Scope

Implement single wrapper for LM Studio OpenAI-compatible API calls.

## Deliverables

- `app/services/llm_client.py`
- request helper
- timeout/error surface
- response text extraction

## Acceptance criteria

- wrapper accepts base URL + model name from config
- simple prompt round-trip works against LM Studio
- failures return actionable errors/logs
