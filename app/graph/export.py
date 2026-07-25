"""Graph export to JSON and static HTML."""

from __future__ import annotations

from dataclasses import dataclass
import html
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GraphExportResult:
    json_path: Path
    html_path: Path


class GraphExporter:
    def __init__(self, project_description_path: Path | None = None) -> None:
        self.project_description_path = project_description_path or Path("project_description.md")

    def export(
        self,
        graph: Any,
        output_dir: Path,
        source_text_by_file: dict[str, str] | None = None,
    ) -> GraphExportResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "graph.json"
        html_path = output_dir / "graph.html"

        payload = {
            "nodes": self._serialize_nodes(graph),
            "edges": self._serialize_edges(graph),
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        html_path.write_text(
            self._build_html(
                payload=payload,
                project_description=self._read_project_description(),
                source_text_by_file=source_text_by_file or {},
            ),
            encoding="utf-8",
        )

        return GraphExportResult(json_path=json_path, html_path=html_path)

    def _serialize_nodes(self, graph: Any) -> list[dict[str, object]]:
        nodes: list[dict[str, object]] = []
        for node_name, attributes in self._iter_nodes(graph):
            gender_inference = attributes.get("gender_inference")
            display_name = self._display_name(node_name)
            node_record = {
                "id": node_name,
                "label": self._node_label(display_name, gender_inference),
                "canonical_name": node_name,
                "aliases": list(attributes.get("aliases", ())),
                "source_files": list(attributes.get("source_files", ())),
                "evidence": list(attributes.get("evidence", ())),
                "gender_inference": gender_inference,
                "centrality_eigenvector": attributes.get("centrality_eigenvector", 0.0),
            }
            nodes.append(node_record)
        return nodes

    def _serialize_edges(self, graph: Any) -> list[dict[str, object]]:
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

    def _build_html(
        self,
        *,
        payload: dict[str, object],
        project_description: str,
        source_text_by_file: dict[str, str],
    ) -> str:
        used_source_files = self._collect_used_source_files(payload)
        used_texts = [
            {"filename": filename, "text": source_text_by_file[filename]}
            for filename in used_source_files
            if filename in source_text_by_file
        ]
        project_description_html = self._markdown_to_html(project_description)
        source_text_sections = "\n".join(
            (
                "<details class=\"source-text\">"
                f"<summary>{html.escape(item['filename'])}</summary>"
                f"<pre>{html.escape(item['text'])}</pre>"
                "</details>"
            )
            for item in used_texts
        ) or "<p>No source texts were attached to this export.</p>"

        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "  <title>Female Character Network Demo</title>\n"
            "  <script src=\"https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js\"></script>\n"
            "  <style>\n"
            "    body { font-family: Arial, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }\n"
            "    main { max-width: 1200px; margin: 0 auto; padding: 24px; }\n"
            "    h1, h2 { margin-bottom: 12px; }\n"
            "    .panel { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 16px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08); }\n"
            "    .controls { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }\n"
            "    .hint { color: #475569; font-size: 0.95rem; }\n"
            "    #graph { width: 100%; height: 780px; border: 1px solid #cbd5e1; border-radius: 12px; background: #ffffff; }\n"
            "    .legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px; }\n"
            "    .legend-item { display: flex; align-items: center; gap: 8px; }\n"
            "    .swatch { width: 14px; height: 14px; border-radius: 999px; display: inline-block; }\n"
            "    pre { white-space: pre-wrap; word-break: break-word; background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; overflow-x: auto; }\n"
            "    code { background: #e2e8f0; padding: 2px 5px; border-radius: 4px; }\n"
            "    .source-text summary { cursor: pointer; font-weight: 600; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <main>\n"
            "    <section class=\"panel\">\n"
            "      <h1>Female Character Network Demo</h1>\n"
            "      <p>This page visualizes co-mentioned characters from the corpus as a network. Female characters are highlighted in pink and shown with underscored labels. Other characters remain in the graph for context.</p>\n"
            "      <div class=\"hint\">Hover over nodes and edges for details. Node size reflects eigenvector centrality. Gender inference is heuristic and should be read as a demo aid, not as definitive annotation.</div>\n"
            "    </section>\n"
            "\n"
            "    <section class=\"panel\">\n"
            "      <h2>Project Description</h2>\n"
            + project_description_html
            + "\n"
            "    </section>\n"
            "\n"
            "    <section class=\"panel\">\n"
            "      <h2>Interactive Graph</h2>\n"
            "      <div class=\"controls\">\n"
            "        <label><input id=\"toggle-non-female\" type=\"checkbox\" checked> Show non-female nodes</label>\n"
            "        <button id=\"fit-graph\" type=\"button\">Fit graph</button>\n"
            "        <span class=\"hint\">Node label = canonical actor name. Female labels are wrapped in underscores.</span>\n"
            "      </div>\n"
            "      <div class=\"legend\">\n"
            "        <div class=\"legend-item\"><span class=\"swatch\" style=\"background:#f472b6\"></span> Female</div>\n"
            "        <div class=\"legend-item\"><span class=\"swatch\" style=\"background:#93c5fd\"></span> Non-female / unresolved</div>\n"
            "      </div>\n"
            "      <div id=\"graph\"></div>\n"
            "    </section>\n"
            "\n"
            "    <section class=\"panel\">\n"
            "      <h2>Source Texts Used in This Graph</h2>\n"
            "      <p class=\"hint\">Only files referenced by graph nodes or edges are shown here.</p>\n"
            + source_text_sections
            + "\n"
            "    </section>\n"
            "\n"
            "    <section class=\"panel\">\n"
            "      <h2>Raw Graph Data</h2>\n"
            "      <pre id=\"graph-data\"></pre>\n"
            "    </section>\n"
            "  </main>\n"
            "\n"
            "  <script>\n"
            "    const graphPayload = "
            + json.dumps(json.dumps(payload, ensure_ascii=False), ensure_ascii=False)
            + ";\n"
            "    const parsedGraphPayload = JSON.parse(graphPayload);\n"
            "    const nodes = parsedGraphPayload.nodes.map((node) => ({\n"
            "      id: node.id,\n"
            "      label: node.label,\n"
            "      title: [\n"
            "        'name: ' + node.label,\n"
            "        'gender: ' + node.gender_inference,\n"
            "        'aliases: ' + (node.aliases.join(', ') || '—'),\n"
            "        'evidence: ' + (node.evidence.join(', ') || '—'),\n"
            "        'centrality: ' + node.centrality_eigenvector,\n"
            "        'source files: ' + (node.source_files.join(', ') || '—'),\n"
            "      ].join('<br>'),\n"
            "      color: node.gender_inference === 'female' ? '#f472b6' : '#93c5fd',\n"
            "      value: Math.max(Number(node.centrality_eigenvector || 0), 0.1) * 100,\n"
            "      shape: 'dot',\n"
            "      hidden: false,\n"
            "      gender_inference: node.gender_inference,\n"
            "    }));\n"
            "    const edges = parsedGraphPayload.edges.map((edge) => ({\n"
            "      from: edge.source,\n"
            "      to: edge.target,\n"
            "      value: edge.weight,\n"
            "      title: [\n"
            "        'weight: ' + edge.weight,\n"
            "        'semantic relation: ' + (edge.semantic_relation || '—'),\n"
            "        'semantic direction: ' + (edge.semantic_direction || '—'),\n"
            "        'semantic confidence: ' + (edge.semantic_confidence ?? '—'),\n"
            "        'source files: ' + (edge.source_files.join(', ') || '—'),\n"
            "      ].join('<br>'),\n"
            "    }));\n"
            "\n"
            "    document.getElementById('graph-data').textContent = JSON.stringify(parsedGraphPayload, null, 2);\n"
            "\n"
            "    const nodeDataSet = new vis.DataSet(nodes);\n"
            "    const edgeDataSet = new vis.DataSet(edges);\n"
            "    const network = new vis.Network(\n"
            "      document.getElementById('graph'),\n"
            "      { nodes: nodeDataSet, edges: edgeDataSet },\n"
            "      {\n"
            "        physics: { stabilization: true },\n"
            "        interaction: { hover: true },\n"
            "        edges: { smooth: false, color: { color: '#64748b' } },\n"
            "      },\n"
            "    );\n"
            "\n"
            "    document.getElementById('toggle-non-female').addEventListener('change', (event) => {\n"
            "      const showNonFemale = event.target.checked;\n"
            "      const updates = nodes.map((node) => ({\n"
            "        id: node.id,\n"
            "        hidden: node.gender_inference === 'female' ? false : !showNonFemale,\n"
            "      }));\n"
            "      nodeDataSet.update(updates);\n"
            "      network.fit();\n"
            "    });\n"
            "\n"
            "    document.getElementById('fit-graph').addEventListener('click', () => {\n"
            "      network.fit();\n"
            "    });\n"
            "\n"
            "    network.fit();\n"
            "  </script>\n"
            "</body>\n"
            "</html>\n"
        )

    def _collect_used_source_files(self, payload: dict[str, object]) -> list[str]:
        filenames: set[str] = set()
        for node in payload["nodes"]:
            filenames.update(node.get("source_files", []))
        for edge in payload["edges"]:
            filenames.update(edge.get("source_files", []))
        return sorted(filenames)

    def _read_project_description(self) -> str:
        if not self.project_description_path.is_file():
            return ""
        return self.project_description_path.read_text(encoding="utf-8")

    def _markdown_to_html(self, text: str) -> str:
        if not text.strip():
            return "<p>Project description not available.</p>"
        lines = text.splitlines()
        html_parts: list[str] = []
        in_list = False
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                continue
            if line.startswith("## "):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append(f"<h3>{html.escape(line[3:])}</h3>")
                continue
            if line.startswith("# "):
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                html_parts.append(f"<h3>{html.escape(line[2:])}</h3>")
                continue
            if line.startswith("* "):
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                html_parts.append(f"<li>{html.escape(line[2:])}</li>")
                continue
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p>{html.escape(line)}</p>")
        if in_list:
            html_parts.append("</ul>")
        return "\n".join(html_parts)

    def _display_name(self, node_name: str) -> str:
        for separator in ("<tab>", "<newline>", "<return>", "\t", "\n", "\r"):
            if separator in node_name:
                node_name = node_name.split(separator, 1)[0]
        return " ".join(node_name.split()).strip() or "[unnamed]"

    def _node_label(self, node_name: str, gender_inference: object) -> str:
        if gender_inference == "female":
            return f"_{node_name}_"
        return node_name

    def _iter_nodes(self, graph: Any):
        if hasattr(graph, "nodes") and callable(getattr(graph.nodes, "data", None)):
            return graph.nodes(data=True)
        return graph.nodes.items()

    def _iter_edges(self, graph: Any):
        if hasattr(graph, "edges") and callable(getattr(graph.edges, "data", None)):
            return graph.edges(data=True)
        return [
            (source, target, attributes)
            for (source, target), attributes in graph.edges.items()
        ]
