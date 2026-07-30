"""Graph pipeline tests."""

# Focused suites intentionally share realistic setup snippets.
from tests.test_support import (
    CanonicalEntity,
    DockerRunResult,
    FakeRunner,
    GraphBuildResult,
    GraphBuilder,
    GraphExportResult,
    GraphExporter,
    Path,
    ProgressReporter,
    ProgressState,
    SemanticEdge,
    handle_run_request,
    json,
    tempfile,
    ScaffoldTestBase,
)


# Graph tests retain small, local entity/edge fixtures so each assertion shows
# its scholarly graph context without hiding it behind a generic factory.
# pylint: disable=duplicate-code
class GraphAndProgressTests(ScaffoldTestBase):
    def test_graph_builder_constructs_graph_and_centrality(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="федосьꙗ",
                aliases=("Федосьꙗ",),
                source_files=("003.003.txt",),
                evidence=("федосьӏ",),
                gender_inference="female",
            ),
        ]
        edges = [
            SemanticEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
                semantic_relation="not stated",
                semantic_direction=None,
                semantic_confidence=0.3,
            ),
            SemanticEdge(
                source="ѥсифъ",
                target="федосьꙗ",
                weight=1,
                source_files=("003.003.txt",),
                semantic_relation="daughter of",
                semantic_direction="target_to_source",
                semantic_confidence=0.6,
            ),
        ]
        result = GraphBuilder().build(entities, edges)

        self.assertIsInstance(result, GraphBuildResult)
        self.assertEqual(set(result.graph.nodes), {"грикша", "ѥсифъ", "федосьꙗ"})
        self.assertEqual(
            {frozenset(edge) for edge in result.graph.edges},
            {frozenset(("грикша", "ѥсифъ")), frozenset(("ѥсифъ", "федосьꙗ"))},
        )
        self.assertEqual(result.graph.nodes["федосьꙗ"]["gender_inference"], "female")
        self.assertIn("centrality_eigenvector", result.graph.nodes["грикша"])
        self.assertEqual(
            result.graph.edges[("ѥсифъ", "федосьꙗ")]["semantic_relation"],
            "daughter of",
        )
        self.assertIn(
            result.warnings,
            ((), ("networkx not available; using fallback eigenvector centrality.",)),
        )

    def test_graph_builder_handles_edgeless_graph(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt",),
                evidence=("грикши",),
                gender_inference="not_inferred",
            )
        ]
        result = GraphBuilder().build(entities, [])

        self.assertEqual(result.centrality, {"грикша": 0.0})
        self.assertIn("Graph has no edges", result.warnings[0])
        self.assertEqual(result.graph.nodes["грикша"]["centrality_eigenvector"], 0.0)

    def test_graph_builder_with_realistic_semantic_edges(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="федосьꙗ",
                aliases=("Федосьꙗ",),
                source_files=("003.003.txt",),
                evidence=("федосьӏ",),
                gender_inference="female",
            ),
            CanonicalEntity(
                canonical_name="петръ",
                aliases=("Петръ",),
                source_files=("004.004.txt",),
                evidence=("петра",),
                gender_inference="not_inferred",
            ),
        ]
        edges = [
            SemanticEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
                semantic_relation="not stated",
                semantic_direction=None,
                semantic_confidence=0.3,
            ),
            SemanticEdge(
                source="ѥсифъ",
                target="федосьꙗ",
                weight=1,
                source_files=("003.003.txt",),
                semantic_relation="daughter of",
                semantic_direction="target_to_source",
                semantic_confidence=0.6,
            ),
            SemanticEdge(
                source="грикша",
                target="петръ",
                weight=1,
                source_files=("004.004.txt",),
                semantic_relation="not stated",
                semantic_direction=None,
                semantic_confidence=0.2,
            ),
        ]
        result = GraphBuilder().build(entities, edges)

        self.assertEqual(result.graph.number_of_nodes(), 4)
        self.assertEqual(result.graph.number_of_edges(), 3)
        self.assertTrue(
            all(node in result.centrality for node in ["грикша", "ѥсифъ", "федосьꙗ", "петръ"])
        )
        self.assertEqual(result.graph.edges[("грикша", "петръ")]["source_files"], ("004.004.txt",))
        self.assertEqual(result.graph.nodes["федосьꙗ"]["aliases"], ("Федосьꙗ",))

    def test_graph_export_writes_json_and_html(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="федосьꙗ",
                aliases=("Федосьꙗ",),
                source_files=("003.003.txt",),
                evidence=("федосьӏ",),
                gender_inference="female",
            ),
        ]
        edges = [
            SemanticEdge(
                source="грикша",
                target="федосьꙗ",
                weight=2,
                source_files=("003.003.txt", "004.004.txt"),
                semantic_relation="not stated",
                semantic_direction=None,
                semantic_confidence=0.4,
            )
        ]
        graph_result = GraphBuilder().build(entities, edges)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = GraphExporter().export(graph_result.graph, Path(temp_dir))
            graph_json = result.json_path.read_text(encoding="utf-8")
            graph_html = result.html_path.read_text(encoding="utf-8")

        self.assertIsInstance(result, GraphExportResult)
        self.assertIn('"nodes"', graph_json)
        self.assertIn('"edges"', graph_json)
        self.assertIn('"centrality_eigenvector"', graph_json)
        self.assertIn('"source_files"', graph_json)
        self.assertIn('грикша', graph_json)
        self.assertIn('"label": "_федосьꙗ_"', graph_json)
        self.assertIn('<html', graph_html.lower())
        self.assertIn('Female Character Network Demo', graph_html)
        self.assertIn('Show non-female nodes', graph_html)

    def test_graph_export_sanitizes_node_labels_for_display(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="кии\tбяше три брата: единому имя кии, второму",
                aliases=("Кии",),
                source_files=("003.003.txt",),
                evidence=("кии",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="лыбедь<tab>бяше три брата: единому имя кии, второму",
                aliases=("Лыбедь",),
                source_files=("003.003.txt",),
                evidence=("лыбедь",),
                gender_inference="female",
            ),
            CanonicalEntity(
                canonical_name="ольга\nкнягиня",
                aliases=("Ольга",),
                source_files=("003.003.txt",),
                evidence=("ольга",),
                gender_inference="female",
            ),
        ]
        graph_result = GraphBuilder().build(entities, [])

        with tempfile.TemporaryDirectory() as temp_dir:
            result = GraphExporter().export(graph_result.graph, Path(temp_dir))
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))

        labels = {node["id"]: node["label"] for node in payload["nodes"]}
        self.assertEqual(
            labels["кии\tбяше три брата: единому имя кии, второму"],
            "кии",
        )
        self.assertEqual(
            labels["лыбедь<tab>бяше три брата: единому имя кии, второму"],
            "_лыбедь_",
        )
        self.assertEqual(labels["ольга\nкнягиня"], "_ольга_")

    def test_graph_export_with_realistic_semantic_graph(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="федосьꙗ",
                aliases=("Федосьꙗ",),
                source_files=("003.003.txt",),
                evidence=("федосьӏ",),
                gender_inference="female",
            ),
        ]
        edges = [
            SemanticEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
                semantic_relation="not stated",
                semantic_direction=None,
                semantic_confidence=0.3,
            ),
            SemanticEdge(
                source="ѥсифъ",
                target="федосьꙗ",
                weight=1,
                source_files=("003.003.txt",),
                semantic_relation="daughter of",
                semantic_direction="target_to_source",
                semantic_confidence=0.6,
            ),
        ]
        graph_result = GraphBuilder().build(entities, edges)

        with tempfile.TemporaryDirectory() as temp_dir:
            exporter_result = GraphExporter().export(graph_result.graph, Path(temp_dir))
            payload = exporter_result.json_path.read_text(encoding="utf-8")
            html = exporter_result.html_path.read_text(encoding="utf-8")

        self.assertIn('"semantic_relation": "daughter of"', payload)
        self.assertIn('"semantic_confidence": 0.6', payload)
        self.assertTrue('"source": "ѥсифъ"' in payload or '"target": "ѥсифъ"' in payload)
        self.assertTrue('"source": "федосьꙗ"' in payload or '"target": "федосьꙗ"' in payload)
        self.assertIn("daughter of", html)
        self.assertIn("003.003.txt", html)
        self.assertIn("Project Description", html)

    def test_progress_reporter_parses_stage_and_counts(self) -> None:
        state = ProgressReporter().from_result(
            stdout=(
                "PROGRESS\tstage=normalization\tcompleted=2\ttotal=5\tstatus=running"
                "\tmessage=Normalizing files\n"
                "PROGRESS\tstage=lemmatization\tcompleted=5\ttotal=5\tstatus=completed"
                "\tmessage=Lemmatization finished\n"
            ),
            stderr="",
            succeeded=True,
        )

        self.assertIsInstance(state, ProgressState)
        self.assertEqual(state.current_stage, "lemmatization")
        self.assertEqual(state.completed_files, 5)
        self.assertEqual(state.total_files, 5)
        self.assertEqual(state.status, "completed")
        self.assertEqual(state.message, "Lemmatization finished")

    def test_progress_reporter_marks_failed_run(self) -> None:
        state = ProgressReporter().from_result(
            stdout=(
                "PROGRESS\tstage=entity_extraction\tcompleted=3\ttotal=5\t"
                "status=running\tmessage=Extracting\n"
            ),
            stderr="container boom",
            succeeded=False,
        )

        self.assertEqual(state.current_stage, "entity_extraction")
        self.assertEqual(state.completed_files, 3)
        self.assertEqual(state.total_files, 5)
        self.assertEqual(state.status, "failed")
        self.assertEqual(state.message, "container boom")

    def test_ui_run_handler_returns_progress_state(self) -> None:
        runner = FakeRunner(
            DockerRunResult(
                command=["docker", "run"],
                returncode=0,
                stdout=(
                    "ok\n"
                    "PROGRESS\tstage=graph_export\tcompleted=5\ttotal=5"
                    "\tstatus=completed\tmessage=Artifacts exported\n"
                ),
                stderr="",
            )
        )

        response = handle_run_request(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            },
            runner=runner,
        )

        self.assertIsNotNone(response.progress_state)
        progress_state = response.progress_state
        if progress_state is None:
            self.fail("expected progress state")
        self.assertEqual(progress_state.current_stage, "graph_export")
        self.assertEqual(progress_state.completed_files, 5)
        self.assertEqual(progress_state.total_files, 5)
        self.assertEqual(progress_state.status, "completed")

    def test_graph_export_json_schema_shape(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt",),
                evidence=("грикши",),
                gender_inference="not_inferred",
            ),
            CanonicalEntity(
                canonical_name="федосьꙗ",
                aliases=("Федосьꙗ",),
                source_files=("003.003.txt",),
                evidence=("федосьӏ",),
                gender_inference="female",
            ),
        ]
        edges = [
            SemanticEdge(
                source="грикша",
                target="федосьꙗ",
                weight=1,
                source_files=("003.003.txt",),
                semantic_relation="daughter of",
                semantic_direction="target_to_source",
                semantic_confidence=0.8,
            )
        ]
        graph_result = GraphBuilder().build(entities, edges)

        with tempfile.TemporaryDirectory() as temp_dir:
            export_result = GraphExporter().export(graph_result.graph, Path(temp_dir))
            payload = json.loads(export_result.json_path.read_text(encoding="utf-8"))

        self.assertEqual(set(payload.keys()), {"nodes", "edges"})
        self.assertEqual(len(payload["nodes"]), 2)
        self.assertEqual(len(payload["edges"]), 1)

        node = payload["nodes"][0]
        self.assertEqual(
            set(node.keys()),
            {
                "id",
                "label",
                "canonical_name",
                "aliases",
                "source_files",
                "evidence",
                "gender_inference",
                "centrality_eigenvector",
            },
        )

        edge = payload["edges"][0]
        self.assertEqual(
            set(edge.keys()),
            {
                "source",
                "target",
                "weight",
                "source_files",
                "semantic_relation",
                "semantic_direction",
                "semantic_confidence",
            },
        )

    def test_smoke_tiny_corpus_happy_path(self) -> None:
        result = self._run_tiny_corpus_pipeline()

        self.assertTrue(result["html_exists"])
        self.assertEqual(len(result["source_files"]), 2)
        self.assertEqual(len(result["normalized_files"]), 2)
        self.assertEqual(len(result["lemmatized_files"]), 2)
        self.assertEqual(len(result["candidates"]), 4)
        self.assertEqual(len(result["entities"]), 3)
        self.assertEqual(len(result["edges"]), 2)
        self.assertEqual(len(result["semantic_edges"]), 2)
        self.assertEqual(len(result["payload"]["nodes"]), 3)
        self.assertEqual(len(result["payload"]["edges"]), 2)
        self.assertEqual(
            {node["id"] for node in result["payload"]["nodes"]},
            {"грикша", "ѥсифъ", "федосьꙗ"},
        )
        self.assertTrue(
            all(
                "centrality_eigenvector" in node
                for node in result["payload"]["nodes"]
            )
        )
        self.assertTrue(
            all("source_files" in node for node in result["payload"]["nodes"])
        )
        self.assertTrue(
            all("source_files" in edge for edge in result["payload"]["edges"])
        )
        self.assertIn("<html", result["html"].lower())
        self.assertIn("Source Texts Used in This Graph", result["html"])
        self.assertIn("003.003.txt", result["html"])
        self.assertIn("Княгиня Грикша пишет к ѥсифу.", result["html"])
