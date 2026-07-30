# Issue Status

Track implementation progress here. Every PR into `dev` must:

1. update `VERSION`, and
2. mark at least 1 issue as completed in this file.

## Implementation issues

- [x] 01 Repository scaffold
- [x] 02 Dependencies and Dockerfile
- [x] 03 Configuration model
- [x] 04 UI shell
- [x] 05 Docker runner
- [x] 06 LLM client wrapper
- [x] 07 File ingestion and original-text logging
- [x] 08 Normalization stage
- [x] 08a Normalization fixtures and regression tests
- [x] 09 Lemmatization stage
- [x] 10 Candidate entity extraction
- [x] 11 Entity merge logic
- [x] 12 Co-occurrence edge generation
- [x] 13 Semantic relation annotation
- [x] 14 Graph builder and centrality
- [x] 15 JSON and HTML export
- [x] 16 Progress reporting
- [x] 17 Smoke tests and schema tests
- [x] 18 Documentation and runbook
- [x] 19 Lemmatized pipeline alignment and quality gates
- [x] 20 LLM-based gender inference for merged entities

## Fix issues

Remediation work is tracked separately from the original implementation sequence.

- [x] 21 PR #2 review iteration 1 remediation (`plan/issues/fix/21_pr2_review_iteration_1.md`)
- [x] 22 PR #22 CI remediation
- [x] 23 PR #2 follow-up review remediation (`plan/issues/fix/23_pr2_review_feedback.md`)
