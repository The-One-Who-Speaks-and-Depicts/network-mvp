"""Co-occurrence edge generation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from app.pipeline.entity_merge import CanonicalEntity


@dataclass(frozen=True)
class CooccurrenceEdge:
    source: str
    target: str
    weight: int
    source_files: tuple[str, ...]


class CooccurrenceService:
    def build_edges(self, entities: list[CanonicalEntity]) -> list[CooccurrenceEdge]:
        grouped: dict[str, list[str]] = {}
        for entity in entities:
            for source_file in entity.source_files:
                grouped.setdefault(source_file, []).append(entity.canonical_name)

        aggregated: dict[tuple[str, str], set[str]] = {}
        for source_file, names in grouped.items():
            unique_names = sorted(set(names))
            for source, target in combinations(unique_names, 2):
                aggregated.setdefault((source, target), set()).add(source_file)

        return [
            CooccurrenceEdge(
                source=source,
                target=target,
                weight=len(source_files),
                source_files=tuple(sorted(source_files)),
            )
            for (source, target), source_files in sorted(aggregated.items())
        ]
