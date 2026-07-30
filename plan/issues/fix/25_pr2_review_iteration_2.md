# Issue 25: PR #2 review iteration 2

## Source

PR #2, “release: promote dev to main”, review submitted on 2026-07-30 at
19:44 UTC. This issue records all nine new inline comments verbatim and one
additional ingestion finding identified while checking their requested scope.

## Comment ledger and remediation

| # | Source | Location | Review comment or finding | Action | Implementation note |
|---:|---|---|---|---|---|
| 1 | PR #2 | `app/pipeline/file_ingestion.py:29` | “very different error types, split them” | Catch filesystem access failures and UTF-8 decoding failures separately during preflight validation. Give each case a plain-language message that identifies whether the file is inaccessible or has invalid encoding. | Implemented in `_read_text`; access failures now report `Could not access corpus file`, while decoding failures report invalid UTF-8. |
| 2 | PR #2 | `app/pipeline/file_ingestion.py:68` | “Also, here and afterwards, split OS/Unicode” | Apply the same separate filesystem/encoding handling in `_read_text`; audit the remainder of `app/` for the same combined handler and add focused tests for both outcomes. | Implemented and covered by separate access and invalid-UTF-8 tests; no other combined filesystem/Unicode handlers remain in `app/`. |
| 3 | PR #2 | `app/pipeline/file_ingestion.py:75` | “try to use some library, or at least justify to me, why you use this” | Retain `pathlib` for exact UTF-8 provenance-artifact writes rather than introducing a logging framework: these files contain source texts and are not application event logs. Add a docstring or rename the helper so that distinction and the direct-write choice are clear to readers. | Added `_write_original_text_artifact()` with a docstring explaining that direct `pathlib` writing preserves exact provenance text and is not event logging. |
| 4 | PR #2 | `app/pipeline/lemmatization.py:50` | “Two very different errors; check the whole code for that” | Split request/provider failures from empty or malformed model output. Preserve per-document isolation, but record a distinct error category and test each path independently. | Split handlers and record `llm_request` versus `invalid_model_output`; both paths have independent assertions. |
| 5 | PR #2 | `app/pipeline/normalization.py:72` | “Once again, here it is possible to see where LlmClientError and ValueError uniting leads” | Split the handlers. Keep the first-request connectivity failure as a run-stopping `NormalizationStageError`, while treating empty/malformed output as a document-level omission; remove the `isinstance` branch made necessary by the combined handler. | Split request and output handlers; only request failure on the first file raises `NormalizationStageError`, and output failures are omitted per document. |
| 6 | PR #2 reply | `app/services/llm_client.py:22` | “Clarify that, why ... is here” | Retain the ellipsis because `PromptingClient` is a structural typing protocol and supplies a signature, not a runtime implementation. Add a concise method docstring explaining that pipeline services accept real clients and test doubles implementing this contract. | Added the protocol method docstring and a precise pylint comment explaining the intentional ellipsis stub. |
| 7 | PR #2 reply | `app/services/llm_client.py:14` | “Once again, no understanding of why this is a specific type” | Retain the project-specific `LlmClientError(RuntimeError)` boundary and expand its documentation: it represents an operational provider/request/response failure, not an invalid caller value, and lets pipeline stages avoid depending on provider-specific exception classes. | Expanded `LlmClientError` documentation to define the operational failure boundary. |
| 8 | PR #2 | `tests/test_graph.py:5` | “I do not like local disabling of pylint, at the very least, give a very good justification” | Run pylint without the module suppression, identify the exact duplicated blocks, and prefer moving genuinely shared setup into `tests/test_support.py`. Retain a narrowly scoped suppression only if the remaining duplication makes individual tests materially easier to read, with an exact rationale rather than a generic comment. | Audited by running pylint without suppressions; retained the module-level suppression with a graph-fixture-specific readability rationale because duplicated fixtures are intentionally local to assertions. |
| 9 | PR #2 | `tests/test_preprocessing.py:5` | “Here and afterwards: I do not like local disabling of pylint, give a very good justification of it.” | Extend the lint-suppression audit to all test modules and other local disables. Remove suppressions made unnecessary by shared helpers; document the precise tradeoff for every retained suppression and keep it as narrow as practical. | Audited all test suppressions; retained precise, module-specific fixture rationales in the four focused suites, while leaving unrelated suppressions unchanged and narrowly scoped. |
| 10 | Additional review | `app/pipeline/file_ingestion.py:25-64` | Each corpus file is fully decoded during `validate_input_directory()` and then decoded again by `load_source_files()`. This doubles ingestion I/O and allows the file to change between validation and use. | Consolidate validation and loading so a service ingestion pass decodes each file once and converts access/encoding failures into the differentiated `InputDirectoryError` contract. Keep the host-side Docker preflight separate because it validates mount inputs before an image build/run. | Removed file decoding from structural preflight; `load_source_files()` now decodes each corpus file once. Docker retains separate host-side directory validation before build/run. |

## Scope decisions

- The combined exception audit currently finds four relevant sites: two
  `OSError`/`UnicodeError` handlers in file ingestion and the
  `LlmClientError`/`ValueError` handlers in normalization and lemmatization.
  Semantic relation handling already separates request and parse failures.
- `LlmClient.prompt()` intentionally catches `Exception` at the external SDK
  boundary because OpenAI-compatible providers can expose different exception
  classes. That boundary should remain broad, chained, and documented; it is
  not equivalent to combining known errors that require different behavior.
- Original-text files under `output/logs/original/` are provenance artifacts,
  not event-log records. A logging library would not replace exact text-file
  export; clearer naming/documentation is the appropriate response.

## Affected files and subsystems

- `app/pipeline/file_ingestion.py`
- `app/pipeline/normalization.py`
- `app/pipeline/lemmatization.py`
- `app/services/llm_client.py`
- `tests/test_graph.py`
- `tests/test_preprocessing.py`
- `tests/test_entities.py`
- `tests/test_runtime.py`
- `tests/test_support.py`
- pylint configuration if a narrowly targeted test policy is necessary

## Acceptance criteria

- All nine PR comments remain represented verbatim in the ledger.
- Filesystem access and UTF-8 decoding failures have distinct messages and
  regression tests.
- LLM request failures and empty/malformed stage outputs use separate handlers,
  retain their intended stop/continue behavior, and have independent tests.
- A service ingestion pass does not decode each source file twice.
- The protocol ellipsis and `LlmClientError` type are understandable without
  requiring knowledge of typing internals or provider SDK exception trees.
- Every local pylint suppression is removed or supported by a precise,
  location-specific justification; shared test helpers are preferred where
  they improve readability.
- Standard unit, pytest, coverage, pylint, mypy, compile, and whitespace checks
  pass and their actual results are recorded during implementation.

## Validation status

Implementation is complete. Validation results:

- `python3 -m unittest discover -s tests -p 'test_*.py' -v`: 82 tests passed.
- `python3 -m pytest -q`: 82 passed, 47 subtests passed.
- Application-only coverage: 85% (required minimum: 80%).
- `python3 -m pylint app tests scripts`: 10.00/10.
- `python3 -m mypy app tests scripts`: passed.
- `python3 -m compileall -q app tests scripts`: passed.
- `git diff --check`: passed.

## Remote review resolution status

The comments were read through the public GitHub API. No conversation has been
resolved and no remote PR state has been changed. Resolve conversations only
after the corresponding repository changes are implemented, pushed, and
verified with authenticated GitHub access.
