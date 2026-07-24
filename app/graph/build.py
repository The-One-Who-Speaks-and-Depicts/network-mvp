"""Graph construction and centrality computation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, cast

try:
    import networkx as NETWORKX
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in local envs
    NETWORKX = None

from app.pipeline.entity_merge import CanonicalEntity
from app.pipeline.semantic_relations import SemanticEdge


class SimpleEdgeView:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], dict[str, object]] = {}

    def add(self, source: str, target: str, attributes: dict[str, object]) -> None:
        self._data[(source, target)] = attributes

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, key: tuple[str, str]) -> dict[str, object]:
        if key in self._data:
            return self._data[key]
        normalized_key = cast(tuple[str, str], tuple(sorted(key)))
        return self._data[normalized_key]

    def __len__(self) -> int:
        return len(self._data)


class SimpleGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, object]] = {}
        self.edges = SimpleEdgeView()

    def add_node(self, node_name: str, **attributes: object) -> None:
        self.nodes[node_name] = dict(attributes)

    def add_edge(self, source: str, target: str, **attributes: object) -> None:
        key = cast(tuple[str, str], tuple(sorted((source, target))))
        self.edges.add(key[0], key[1], dict(attributes))

    def number_of_nodes(self) -> int:
        return len(self.nodes)

    def number_of_edges(self) -> int:
        return len(self.edges)


@dataclass(frozen=True)
class GraphBuildResult:
    graph: Any
    centrality: dict[str, float]
    warnings: tuple[str, ...]


class GraphBuilder:
    def build(
        self,
        entities: list[CanonicalEntity],
        edges: list[SemanticEdge],
    ) -> GraphBuildResult:
        graph = NETWORKX.Graph() if NETWORKX is not None else SimpleGraph()

        for entity in entities:
            graph.add_node(
                entity.canonical_name,
                aliases=entity.aliases,
                source_files=entity.source_files,
                evidence=entity.evidence,
                gender_inference=entity.gender_inference,
            )

        for edge in edges:
            graph.add_edge(
                edge.source,
                edge.target,
                weight=edge.weight,
                source_files=edge.source_files,
                semantic_relation=edge.semantic_relation,
                semantic_direction=edge.semantic_direction,
                semantic_confidence=edge.semantic_confidence,
            )

        warnings: list[str] = []
        centrality = self._compute_centrality(graph, warnings)

        for node_name, node_centrality in centrality.items():
            graph.nodes[node_name]["centrality_eigenvector"] = node_centrality

        return GraphBuildResult(
            graph=graph,
            centrality=centrality,
            warnings=tuple(warnings),
        )

    def _compute_centrality(self, graph: Any, warnings: list[str]) -> dict[str, float]:
        if graph.number_of_nodes() == 0:
            warnings.append("Graph has no nodes; centrality skipped.")
            return {}

        if graph.number_of_edges() == 0:
            warnings.append("Graph has no edges; centrality defaults to 0.0 for all nodes.")
            return {node: 0.0 for node in graph.nodes}

        if NETWORKX is not None:
            try:
                return cast(
                    dict[str, float],
                    NETWORKX.eigenvector_centrality(graph, weight="weight", max_iter=1000),
                )
            except NETWORKX.NetworkXException as error:
                warnings.append(f"Eigenvector centrality failed: {error}")
                return {node: 0.0 for node in graph.nodes}

        warnings.append("networkx not available; using fallback eigenvector centrality.")
        return self._fallback_eigenvector_centrality(graph)

    def _fallback_eigenvector_centrality(self, graph: SimpleGraph) -> dict[str, float]:
        nodes = list(graph.nodes)
        index = {node: position for position, node in enumerate(nodes)}
        values = [1.0 for _ in nodes]

        for _ in range(100):
            next_values = [0.0 for _ in nodes]
            for (source, target), attributes in graph.edges.items():
                weight = float(cast(float | int | str, attributes.get("weight", 1.0)))
                source_index = index[source]
                target_index = index[target]
                next_values[source_index] += weight * values[target_index]
                next_values[target_index] += weight * values[source_index]

            norm = math.sqrt(sum(value * value for value in next_values))
            if norm == 0.0:
                return {node: 0.0 for node in nodes}

            next_values = [value / norm for value in next_values]
            max_delta = max(
                abs(current - next_value)
                for current, next_value in zip(values, next_values)
            )
            values = next_values
            if max_delta < 1e-9:
                break

        return {node: values[index[node]] for node in nodes}
