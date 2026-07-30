# Issue 23: PR #2 review feedback

## Source

Follow-up review of PR #2, “release: promote dev to main”. The review focused on runtime safety, semantic clarity, CI quality gates, and documentation for domain specialists.

## Remediation

- Validate corpus directories before running the pipeline; reject missing, empty, unreadable, and non-UTF-8 input with a plain-language failure.
- Define and validate semantic direction values: `source_to_target`, `target_to_source`, or no direction for `not stated`.
- Update README and RUNBOOK to describe the configured end-to-end pipeline, its prerequisites, outputs, scaffold smoke mode, and manual review responsibilities.
- Synchronize the repository development version and release-tracking documentation.
- Measure application coverage with `--source=app` so tests do not inflate the quality gate.
- Upgrade GitHub Actions checkout steps to `actions/checkout@v5`.
- Make `NETWORK_MVP_ENABLE_DEBUG_LOGGING` configure application logging and document that messages appear on container stderr.
- Split the monolithic scaffold test module into focused preprocessing, entity/relation, graph/progress, runtime, and documentation suites with shared fixtures in `tests/test_support.py`.

## Validation

The affected runtime paths have regression tests for invalid corpus directories and invalid relation directions. The standard compile, unit-test, coverage, pylint, mypy, and diff checks must pass before merge. Test discovery now runs 71 tests across focused modules.

## Remote PR description

The original PR description is remote GitHub metadata and requires authenticated GitHub write access to update. Repository documentation is synchronized locally; update the PR description when authenticated access is available.
