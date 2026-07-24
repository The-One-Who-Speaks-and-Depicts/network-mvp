# CI Checklist

## Automated checks

CI should verify:

- Python sources compile
- unit/smoke tests pass
- `pylint` passes
- `mypy` passes
- no Python cache artifacts are tracked
- every PR into `dev` changes `VERSION`
- every PR into `dev` updates `plan/issue_status.md`
- every PR into `dev` marks at least one issue as completed in `plan/issue_status.md`

## Human review checklist

Before merging into `dev`, verify:

- scope matches exactly one issue-sized task, or a tightly related slice
- implementation matches acceptance criteria for targeted issue
- plan status reflects real completion, not partial progress
- version bump is intentional and unique
- PR exists with clear title and description
- changed logic has tests with realistic mocks or real domain fixtures where practical
- local `pylint` and `mypy` pass for touched scope where environment supports them
- CI is green
