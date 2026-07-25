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
9. `08a_normalization_fixtures.md`
10. `09_lemmatization_stage.md`
11. `10_entity_extraction.md`
12. `11_entity_merge_logic.md`
13. `12_cooccurrence_edges.md`
14. `13_semantic_relation_annotation.md`
15. `14_graph_builder.md`
16. `15_export_json_and_html.md`
17. `16_progress_reporting.md`
18. `17_tests_smoke_and_schema.md`
19. `18_docs_and_runbook.md`
20. `19_lemma_pipeline_and_quality_gates.md`
21. `20_llm_gender_inference.md`

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
