"""Entity merge logic for canonical graph nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.pipeline.entities import CandidateEntity
from app.services.llm_client import LlmClientError, PromptingClient


@dataclass(frozen=True)
class CanonicalEntity:
    canonical_name: str
    aliases: tuple[str, ...]
    source_files: tuple[str, ...]
    evidence: tuple[str, ...]
    gender_inference: str


@dataclass
class _MergeAccumulator:
    aliases: set[str] = field(default_factory=set)
    source_files: set[str] = field(default_factory=set)
    evidence: set[str] = field(default_factory=set)


class EntityMergeService:
    def __init__(
        self,
        llm_client: PromptingClient | None = None,
        prompt_template_path: Path | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_template_path = (
            prompt_template_path or Path("prompts/entity_gender_prompt.txt")
        )

    def merge_candidates(self, candidates: list[CandidateEntity]) -> list[CanonicalEntity]:
        merged: dict[str, _MergeAccumulator] = {}

        for candidate in candidates:
            canonical_name = self._canonicalize_name(candidate.name)
            if canonical_name not in merged:
                merged[canonical_name] = _MergeAccumulator()

            merged[canonical_name].aliases.add(candidate.name)
            merged[canonical_name].source_files.add(candidate.filename)
            merged[canonical_name].evidence.add(candidate.evidence)

        prompt_template = self._read_gender_prompt_template()
        return [
            CanonicalEntity(
                canonical_name=canonical_name,
                aliases=tuple(sorted(data.aliases)),
                source_files=tuple(sorted(data.source_files)),
                evidence=tuple(sorted(data.evidence)),
                gender_inference=self._infer_entity_gender(
                    canonical_name,
                    data,
                    prompt_template,
                ),
            )
            for canonical_name, data in sorted(merged.items())
        ]

    def _canonicalize_name(self, name: str) -> str:
        sanitized = self._sanitize_name(name.lower())
        for prefix in ("князь ", "княгиня ", "господин ", "госпожа "):
            if sanitized.startswith(prefix):
                sanitized = sanitized[len(prefix):]
        return sanitized

    def _sanitize_name(self, name: str) -> str:
        for separator in ("<tab>", "<newline>", "<return>", "\t", "\n", "\r"):
            if separator in name:
                name = name.split(separator, 1)[0]
        return " ".join(name.split()).strip()

    def _read_gender_prompt_template(self) -> str | None:
        if self.llm_client is None or not self.prompt_template_path.is_file():
            return None
        return self.prompt_template_path.read_text(encoding="utf-8")

    def _infer_entity_gender(
        self,
        canonical_name: str,
        data: _MergeAccumulator,
        prompt_template: str | None,
    ) -> str:
        heuristic_gender = self._infer_gender_from_aliases(data.aliases)
        if self.llm_client is None or prompt_template is None:
            return heuristic_gender

        prompt = prompt_template.format(
            canonical_name=canonical_name,
            aliases="\n".join(sorted(data.aliases)) or "—",
            evidence="\n".join(sorted(data.evidence)) or "—",
            source_files="\n".join(sorted(data.source_files)) or "—",
        )
        try:
            response = self.llm_client.prompt(prompt)
        except LlmClientError:
            return heuristic_gender

        parsed_gender = self._parse_gender_response(response.text)
        if parsed_gender is None:
            return heuristic_gender
        return parsed_gender

    def _infer_gender_from_aliases(self, aliases: set[str]) -> str:
        inferred = "not-inferred"
        for alias in sorted(aliases):
            inferred = self._merge_gender(inferred, self._infer_gender_from_name(alias))
        return inferred

    def _infer_gender_from_name(self, name: str) -> str:
        lowered = self._sanitize_name(name.lower())
        if lowered.startswith(("княгиня ", "госпожа ")):
            return "female"
        if lowered.endswith(("а", "ѧ", "ꙗ")):
            return "female"
        if lowered.endswith(("ъ", "ь")):
            return "not-inferred"
        if lowered:
            return "unresolved"
        return "not-inferred"

    def _parse_gender_response(self, response_text: str) -> str | None:
        for raw_line in response_text.splitlines():
            label = raw_line.strip().lower().split("\t", 1)[0].strip()
            if label in {"female", "ambiguous", "unresolved", "not-inferred"}:
                return label
        return None

    def _merge_gender(self, existing: str, incoming: str) -> str:
        if existing == incoming:
            return existing
        if "ambiguous" in {existing, incoming}:
            return "ambiguous"
        if "female" in {existing, incoming}:
            return "female"
        if "unresolved" in {existing, incoming}:
            return "unresolved"
        return "not-inferred"
