"""Check pull requests for required project governance updates."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

VERSION_FILE = Path("VERSION")
ISSUE_STATUS_FILE = Path("plan/issue_status.md")
CHECKBOX_RE = re.compile(r"^- \[(?P<state>[ xX])\] (?P<label>.+)$")


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def read_file_from_ref(ref: str, path: Path) -> str:
    try:
        return run_git("show", f"{ref}:{path.as_posix()}")
    except subprocess.CalledProcessError:
        return ""


def parse_checklist(text: str) -> dict[str, bool]:
    parsed: dict[str, bool] = {}
    for line in text.splitlines():
        match = CHECKBOX_RE.match(line.strip())
        if match:
            parsed[match.group("label")] = match.group("state").lower() == "x"
    return parsed


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main() -> int:
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if not base_ref:
        print("No GITHUB_BASE_REF set; skipping PR governance checks.")
        return 0

    base_remote_ref = f"origin/{base_ref}"
    merge_base = run_git("merge-base", "HEAD", base_remote_ref)
    changed_files = set(run_git("diff", "--name-only", f"{merge_base}...HEAD").splitlines())

    if VERSION_FILE.as_posix() not in changed_files:
        return fail("PR into dev must update VERSION.")

    if ISSUE_STATUS_FILE.as_posix() not in changed_files:
        return fail("PR into dev must update plan/issue_status.md.")

    base_text = read_file_from_ref(merge_base, ISSUE_STATUS_FILE)
    head_text = ISSUE_STATUS_FILE.read_text(encoding="utf-8")

    base_checks = parse_checklist(base_text)
    head_checks = parse_checklist(head_text)

    completed_now = [
        label
        for label, is_checked in head_checks.items()
        if is_checked and not base_checks.get(label, False)
    ]

    if not completed_now:
        return fail(
            "PR into dev must mark at least one issue as completed in plan/issue_status.md."
        )

    print("PR governance checks passed.")
    print("Completed in this PR:")
    for label in completed_now:
        print(f"- {label}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
