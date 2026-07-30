# Fix-Issue Instructions

Use this folder for remediation work that follows code review, pull-request feedback, quality-gate failures, or regression findings. Fix issues remain separate from the original implementation sequence.

## Create a fix issue

1. Choose the next available issue number and use the filename format `NN_short_description.md`.
2. Record the source: pull request, review date, issue, quality tool, or regression report.
3. Copy every source comment or finding into a comment ledger. Do not silently merge, omit, or paraphrase distinct findings.
4. Add an action for each finding and leave an implementation note describing exactly what was changed.
5. Add acceptance criteria and identify the affected files or subsystem.

## Implement consecutively

Work through the ledger in order. For each item:

- inspect the relevant code and tests;
- make the smallest coherent change that addresses the finding;
- add or update regression coverage where behavior changes;
- record the result in the implementation-note column;
- keep unrelated refactors out of the fix issue.

If a comment is intentionally not implemented, document the reason and the retained behavior instead of marking it silently complete.

## Validate

Run checks appropriate to the issue and record their results. For the standard Python project, run:

```text
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m pytest -q
python3 -m coverage run --source=app -m unittest discover -s tests -p 'test_*.py'
python3 -m coverage report --fail-under=80
python3 -m pylint app tests scripts
python3 -m mypy app tests scripts
python3 -m compileall -q app tests scripts
```

Also run `git diff --check`. If a tool is unavailable or reports unrelated baseline findings, record that fact explicitly and do not claim the gate passed.

## Update tracking

- Add the fix issue to `plan/issues/fix/00_fix_issue_index.md`.
- Add or update its checkbox under the `Fix issues` section of `plan/issue_status.md`.
- Keep the original implementation issue statuses unchanged.
- Link the fix issue from any relevant project or review documentation.

## Remote review resolution

Repository changes and remote conversation resolution are separate actions. After the branch is pushed and the review has been addressed, resolve the corresponding GitHub conversations when authenticated access is available. If access is unavailable, record that the repository-side fix is complete and that remote resolution is pending; never claim the remote thread was resolved.

## Completion checklist

- [ ] Every source comment or finding is listed.
- [ ] Every ledger row has an implementation note.
- [ ] Acceptance criteria are satisfied.
- [ ] Relevant tests and quality checks pass.
- [ ] Index and status files are updated.
- [ ] Remote conversation status is accurately recorded.
