"""Semantic relation annotation for co-occurrence edges."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.pipeline.cooccurrence import CooccurrenceEdge
from app.services.llm_client import LlmClientError, PromptingClient


ALLOWED_RELATIONS = {
    "princess of",
    "wife of",
    "daughter of",
    "mother of",
    "sister of",
    "grandmother of",
    "aunt of",
    "granddaughter of",
    "in-law of",
    "prince of",
    "husband of",
    "son of",
    "father of",
    "brother of",
    "grandfather of",
    "uncle of",
    "grandson of",
    "not stated",
}


@dataclass(frozen=True)
class SemanticEdge:
    source: str
    target: str
    weight: int
    source_files: tuple[str, ...]
    semantic_relation: str | None = None
    semantic_direction: str | None = None
    semantic_confidence: float | None = None


class SemanticRelationService:
    def __init__(
        self,
        llm_client: PromptingClient,
        prompt_template_path: Path | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_template_path = prompt_template_path or Path("prompts/semantic_relation_prompt.txt")

    def annotate_edges(
        self,
        edges: list[CooccurrenceEdge],
        lemmatized_context_by_file: dict[str, str],
        enabled: bool = True,
        source_context_by_file: dict[str, str] | None = None,
    ) -> list[SemanticEdge]:
        if not enabled:
            return [self._to_semantic_edge(edge) for edge in edges]

        prompt_template = self.prompt_template_path.read_text(encoding="utf-8")
        annotated: list[SemanticEdge] = []
        source_context_lookup = source_context_by_file or {}

        for edge in edges:
            lemmatized_context = "\n".join(
                lemmatized_context_by_file[source_file]
                for source_file in edge.source_files
                if source_file in lemmatized_context_by_file
            )
            source_context = "\n".join(
                source_context_lookup[source_file]
                for source_file in edge.source_files
                if source_file in source_context_lookup
            )
            prompt = prompt_template.format(
                lemma_context=lemmatized_context,
                source_context=source_context or lemmatized_context,
                source=edge.source,
                target=edge.target,
            )

            try:
                response = self.llm_client.prompt(prompt)
                relation, direction, confidence = self._parse_response(response.text)
            except (LlmClientError, ValueError):
                annotated.append(self._to_semantic_edge(edge, relation="not stated", direction=None, confidence=0.0))
                continue

            annotated.append(
                self._to_semantic_edge(
                    edge,
                    relation=relation,
                    direction=direction,
                    confidence=confidence,
                )
            )

        return annotated

    def _parse_response(self, response_text: str) -> tuple[str, str | None, float]:
        first_line = next((line.strip() for line in response_text.splitlines() if line.strip()), "")
        parts = first_line.split("\t")
        if len(parts) != 3:
            raise ValueError("invalid semantic annotation format")

        relation = parts[0].strip()
        direction = parts[1].strip() or None
        try:
            confidence = float(parts[2].strip())
        except ValueError as error:
            raise ValueError("invalid semantic annotation confidence") from error

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("invalid semantic annotation confidence range")

        if relation not in ALLOWED_RELATIONS:
            return "not stated", None, 0.0

        return relation, direction, confidence

    def _to_semantic_edge(
        self,
        edge: CooccurrenceEdge,
        relation: str | None = None,
        direction: str | None = None,
        confidence: float | None = None,
    ) -> SemanticEdge:
        return SemanticEdge(
            source=edge.source,
            target=edge.target,
            weight=edge.weight,
            source_files=edge.source_files,
            semantic_relation=relation,
            semantic_direction=direction,
            semantic_confidence=confidence,
        )
