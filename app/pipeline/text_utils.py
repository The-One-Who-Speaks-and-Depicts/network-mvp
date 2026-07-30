"""Shared text cleanup helpers used by LLM-backed preprocessing stages."""

from __future__ import annotations


def sanitize_output(text: str) -> str:
    """Collapse model whitespace so downstream stages receive one-line text."""

    return " ".join(text.split())
