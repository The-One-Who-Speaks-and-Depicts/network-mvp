"""Graph export to JSON and static HTML."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

try:
    from pyvis.network import Network
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in local envs
    Network = None


@dataclass(frozen=True)
class GraphExportResult:
    json_path: Path
    html_path: Path


class GraphExporter:
    def export(self, graph: object, output_dir: Path) -> GraphExportResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "graph.json"
        html_path = output_dir / "graph.html"

        payload = {
            "nodes": self._serialize_nodes(graph),
            "edges": self._serialize_edges(graph),
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_html(graph, html_path)

        return GraphExportResult(json_path=json_path, html_path=html_path)

    def _serialize_nodes(self, graph: object) -> list[dict[str, object]]:
        nodes: list[dict[str, object]] = []
        for node_name, attributes in self._iter_nodes(graph):
            node_record = {
                "id": node_name,
                "label": node_name,
                "aliases": list(attributes.get("aliases", ())),
                "source_files": list(attributes.get("source_files", ())),
                "evidence": list(attributes.get("evidence", ())),
                "gender_inference": attributes.get("gender_inference"),
                "centrality_eigenvector": attributes.get("centrality_eigenvector", 0.0),
            }
            nodes.append(node_record)
        return nodes

    def _serialize_edges(self, graph: object) -> list[dict[str, object]]:
        edges: list[dict[str, object]] = []
        for source, target, attributes in self._iter_edges(graph):
            edge_record = {
                "source": source,
                "target": target,
                "weight": attributes.get("weight", 1),
                "source_files": list(attributes.get("source_files", ())),
                "semantic_relation": attributes.get("semantic_relation"),
                "semantic_direction": attributes.get("semantic_direction"),
                "semantic_confidence": attributes.get("semantic_confidence"),
            }
            edges.append(edge_record)
        return edges

    def _write_html(self, graph: object, html_path: Path) -> None:
        if Network is None:
            html_path.write_text(self._fallback_html(graph), encoding="utf-8")
            return

        network = Network(height="750px", width="100%", bgcolor="#ffffff", font_color="#000000")
        for node_name, attributes in self._iter_nodes(graph):
            centrality = attributes.get("centrality_eigenvector", 0.0)
            source_files = tuple(attributes.get("source_files", ()))
            title = (
                f"label: {node_name}<br>"
                f"gender: {attributes.get('gender_inference')}<br>"
                f"centrality: {centrality}<br>"
                f"source files: {len(source_files)}<br>"
                f"references: {', '.join(source_files)}"
            )
            network.add_node(
                node_name,
                label=node_name,
                title=title,
                color="#f472b6" if attributes.get("gender_inference") == "female" else "#93c5fd",
                value=max(float(centrality), 0.1) * 100,
            )

        for source, target, attributes in self._iter_edges(graph):
            title_parts = [
                f"weight: {attributes.get('weight', 1)}",
                f"references: {', '.join(attributes.get('source_files', ()))}",
            ]
            if attributes.get("semantic_relation"):
                title_parts.append(f"semantic relation: {attributes.get('semantic_relation')}")
            if attributes.get("semantic_confidence") is not None:
                title_parts.append(f"semantic confidence: {attributes.get('semantic_confidence')}")
            network.add_edge(source, target, value=attributes.get("weight", 1), title="<br>".join(title_parts))

        network.write_html(str(html_path), notebook=False)

    def _fallback_html(self, graph: object) -> str:
        payload = {
            "nodes": self._serialize_nodes(graph),
            "edges": self._serialize_edges(graph),
        }
        return """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Network Graph</title>
</head>
<body>
  <h1>Network Graph</h1>
  <pre id=\"graph-data\"></pre>
  <script>
    const graphData = """ + json.dumps(json.dumps(payload, ensure_ascii=False, indent=2), ensure_ascii=False) + """;
    document.getElementById('graph-data').textContent = graphData;
  </script>
</body>
</html>
"""

    def _iter_nodes(self, graph: object):
        if hasattr(graph, "nodes") and callable(getattr(graph.nodes, "data", None)):
            return graph.nodes(data=True)
        return graph.nodes.items()

    def _iter_edges(self, graph: object):
        if hasattr(graph, "edges") and callable(getattr(graph.edges, "data", None)):
            return graph.edges(data=True)
        return [(source, target, attributes) for (source, target), attributes in graph.edges._data.items()]
