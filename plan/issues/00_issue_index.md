# Issue-Sized Task Index

Goal: keep implementation sliced into small, context-safe units that can be completed without long prompts or large cross-file reasoning.

## Recommended order

1. `01_repo_scaffold.md`
2. `02_dependencies_and_dockerfile.md`
3. `03_config_model.md`
4. `04_ui_shell.md`
5. `05_docker_runner.md`
6. `06_llm_client.md`
7. `07_file_ingestion_and_logging.md`
8. `08_normalization_stage.md`
9. `09_lemmatization_stage.md`
10. `10_entity_extraction.md`
11. `11_entity_merge_logic.md`
12. `12_cooccurrence_edges.md`
13. `13_semantic_relation_annotation.md`
14. `14_graph_builder.md`
15. `15_export_json_and_html.md`
16. `16_progress_reporting.md`
17. `17_tests_smoke_and_schema.md`
18. `18_docs_and_runbook.md`

## Rules for each issue

- keep scope to 1 bounded deliverable
- prefer 1-4 files changed
- include explicit acceptance criteria
- avoid combining UI + pipeline + export changes in 1 issue
- merge only after local smoke test for affected area

## Suggested labels

- `infra`
- `ui`
- `pipeline`
- `llm`
- `graph`
- `export`
- `test`
- `docs`
- `mvp`
