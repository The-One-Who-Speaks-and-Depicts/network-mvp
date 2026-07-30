# Issue 21: PR #2 review iteration 1

## Source

PR #2, “release: promote dev to main”, reviewed on 2026-07-30. This issue tracks all 20 inline review comments and is ordered so each item can be implemented and checked consecutively.

## Comment ledger and remediation

| # | Location | Review comment | Action | Implementation performed |
|---:|---|---|---|---|
| 1 | `.github/workflows/ci.yml:7` | “not necessary tbh, but add to main” | Add `main` to push validation branches. | Added `main` to the workflow push branch list. |
| 2 | `.github/workflows/ci.yml:40` | “Add coverage” | Install `coverage`, run the test suite under coverage, and enforce an 80% minimum. | Added the `coverage` dependency and a CI coverage run with `--fail-under=80`. |
| 3 | `.github/workflows/ci.yml:64` | “not necessary, the pipeline is always feat > dev” | Remove `feat/**` push triggers; feature branches are validated through PRs into `dev`. | Removed the `feat/**` push trigger. |
| 4 | `app/graph/build.py:12` | “not needed honestly” | Retain the optional NetworkX fallback because it supports minimal installs; document that decision inline. | Kept the fallback and documented its minimal-install/recovery-image purpose. |
| 5 | `app/graph/build.py:34` | “I do not understand this construction” | Name and document the undirected edge-key normalization. | Added an explanatory comment for sorting endpoints into one undirected key. |
| 6 | `app/graph/build.py:50` | “once again here” | Centralize the same edge-key construction in a named helper. | Added `SimpleGraph._edge_key()` and routed edge insertion through it. |
| 7 | `app/graph/build.py:73` | “what?” | Explain graph backend selection and its fallback purpose. | Documented the NetworkX-versus-`SimpleGraph` selection. |
| 8 | `app/graph/build.py:116` | “Once again, what is it?” | Explain the NetworkX centrality call and failure behavior. | Documented weighted eigenvector centrality and the zero-value failure fallback. |
| 9 | `app/pipeline/entities.py:51` | “No logging, no anything?” | Log extraction failures with file identity before continuing. | Added a warning containing file ID, filename, and the client error. |
| 10 | `app/pipeline/entity_merge.py:104` | “wow, no logging, no anything here, shall we correct that?” | Log LLM gender-inference failures before heuristic fallback. | Added a warning containing canonical name and the fallback error. |
| 11 | `app/pipeline/entity_merge.py:112` | “underscore instead of hyphen, please” | Rename the status value to `not_inferred`. | Renamed the status in entity merge logic. |
| 12 | `app/pipeline/entity_merge.py:112` | “for all the instances” | Apply `not_inferred` consistently in code, prompt, tests, and documentation. | Updated all repository occurrences, including tests, prompt, README, and project docs. |
| 13 | `app/pipeline/lemmatization.py:36` | “Why do we not use something like os path join?” | Use `Path.joinpath`, the pathlib equivalent already used by the service. | Replaced the output-path expression with `lemma_dir.joinpath(...)`. |
| 14 | `app/pipeline/lemmatization.py:51` | “I am not sure we should continue here” | Keep processing later files after a malformed response, while recording the failure as before. | Preserved per-file logging and continuation, and documented that isolation behavior inline. |
| 15 | `app/pipeline/normalization.py:116` | “should not we unify them somehow with the ones in lemmatisation?” | Extract shared whitespace sanitization into `text_utils.py`. | Added `app/pipeline/text_utils.py` and reused it from both stages. |
| 16 | `app/pipeline/semantic_relations.py:103` | “As said before, I do not like joining LlmClientError and ValueError together, especially without any kind of logging. I do not like try-catching here in general, it seems like not a genuine try-catch, but a malpractice” | Catch `LlmClientError` and `ValueError` separately, log each, and use the explicit fallback. | Split the handlers, added contextual warnings, and retained the safe `not stated` edge fallback. |
| 17 | `app/pipeline/semantic_relations.py:146` | “Log something here” | Log invalid relation responses with edge identity and error detail. | Added invalid-response warnings with source and target edge names. |
| 18 | `app/services/llm_client.py:20` | “what is that, exactly?” | Document the provider-neutral prompting protocol and response wrapper. | Added docstrings to `PromptingClient` and `LlmResponse`. |
| 19 | `app/services/llm_client.py:14` | “No comments, no anything?” | Add concise class/method documentation for the client contract and error boundary. | Documented `LlmClient` and its `prompt()` error contract. |
| 20 | `app/ui/app.py:18` | “Clarify this” | Explain why direct Streamlit script execution needs the repository root on `sys.path`. | Added the explanation above the direct-execution import-path adjustment. |

## Acceptance criteria

- Every PR #2 inline comment appears in the ledger above.
- CI validates `main` pushes, tests coverage, and does not run redundant feature-branch pushes.
- Pipeline fallbacks are observable through logs and retain their safe behavior.
- Shared preprocessing behavior has one implementation.
- Status labels use `not_inferred` consistently.
- The affected test, lint, type, and compile checks pass.

## Follow-up quality-tool note

Installed the CI-compatible `coverage`, `pylint`, and `mypy` versions locally, plus project runtime dependencies. The first run exposed existing style/type findings; this follow-up pass fixes those findings. Final validation: pylint 10.00/10, mypy clean, 67 unittest tests passed, 67 pytest tests passed, and coverage 94%.

## Remote PR resolution status

All 20 comments are resolved in the repository implementation and documented above. Marking the GitHub conversations as resolved requires authenticated GitHub write access; this environment has no `GH_TOKEN` and `gh auth status` reports no logged-in account. No remote PR state was changed.
