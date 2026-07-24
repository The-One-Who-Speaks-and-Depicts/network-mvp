"""Entity merge logic for canonical graph nodes."""

from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.entities import CandidateEntity


@dataclass(frozen=True)
class CanonicalEntity:
    canonical_name: str
    aliases: tuple[str, ...]
    source_files: tuple[str, ...]
    evidence: tuple[str, ...]
    gender_inference: str


class EntityMergeService:
    def merge_candidates(self, candidates: list[CandidateEntity]) -> list[CanonicalEntity]:
        merged: dict[str, dict[str, set[str] | str]] = {}

        for candidate in candidates:
            canonical_name = self._canonicalize_name(candidate.name)
            if canonical_name not in merged:
                merged[canonical_name] = {
                    "aliases": set(),
                    "source_files": set(),
                    "evidence": set(),
                    "gender_inference": self._infer_gender(candidate.name),
                }

            merged[canonical_name]["aliases"].add(candidate.name)
            merged[canonical_name]["source_files"].add(candidate.filename)
            merged[canonical_name]["evidence"].add(candidate.evidence)

        return [
            CanonicalEntity(
                canonical_name=canonical_name,
                aliases=tuple(sorted(data["aliases"])),
                source_files=tuple(sorted(data["source_files"])),
                evidence=tuple(sorted(data["evidence"])),
                gender_inference=str(data["gender_inference"]),
            )
            for canonical_name, data in sorted(merged.items())
        ]

    def _canonicalize_name(self, name: str) -> str:
        sanitized = " ".join(name.lower().split())
        for prefix in ("князь ", "княгиня ", "господин ", "госпожа "):
            if sanitized.startswith(prefix):
                sanitized = sanitized[len(prefix):]
        return sanitized

    def _infer_gender(self, name: str) -> str:
        lowered = name.lower()
        if lowered.endswith(("а", "ѧ", "ꙗ")):
            return "female"
        if lowered.endswith(("ъ", "ь")):
            return "not-inferred"
        return "not-inferred"
