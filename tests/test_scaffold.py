"""Scaffold and regression tests for application modules."""

import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from app import main as app_main
from app.services import llm_client as llm_client_module

from app.config import AppConfig, ConfigError
from app.graph.build import GraphBuildResult, GraphBuilder
from app.graph.export import GraphExportResult, GraphExporter
from app.progress.reporting import ProgressReporter, ProgressState
from app.pipeline.cooccurrence import CooccurrenceEdge, CooccurrenceService
from app.pipeline.entities import CandidateEntity, EntityExtractionService
from app.pipeline.semantic_relations import SemanticEdge, SemanticRelationService
from app.pipeline.entity_merge import CanonicalEntity, EntityMergeService
from app.pipeline.file_ingestion import FileIngestionService, SourceFile
from app.pipeline.lemmatization import LemmatizationService, LemmatizedFile
from app.pipeline.normalization import (
    NormalizationService,
    NormalizedFile,
    NormalizationStageError,
)
from app.services.docker_runner import DockerRunResult, DockerRunner
from app.services.llm_client import LlmClient, LlmClientError, LlmResponse
from app.ui.shell import UiDefaults, UiRunResponse, default_form_values, handle_run_request


class FakeRunner(DockerRunner):
    def __init__(self, result: DockerRunResult) -> None:
        super().__init__(image_name="network-mvp:test")
        self.result = result
        self.received_config: AppConfig | None = None

    def run(self, config: AppConfig) -> DockerRunResult:
        self.received_config = config
        return self.result


class FakeCompletions:
    def __init__(self, response: object | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = type("Chat", (), {"completions": completions})()


class FakeMessage:
    def __init__(self, content: object) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: object) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: object) -> None:
        self.choices = [FakeChoice(content)]


class FakeLlmClient:
    def __init__(self, responses: list[str] | None = None, error: Exception | None = None) -> None:
        self.responses = responses or []
        self.error = error
        self.prompts: list[str] = []

    def prompt(self, prompt_text: str, _system_prompt: str | None = None) -> LlmResponse:
        self.prompts.append(prompt_text)
        if self.error is not None:
            raise self.error
        if not self.responses:
            return LlmResponse(text="", raw_response=None)
        return LlmResponse(text=self.responses.pop(0), raw_response=None)


class ScaffoldTests(unittest.TestCase):
    def _tiny_corpus_clients(self) -> dict[str, FakeLlmClient]:
        return {
            "normalization": FakeLlmClient(
                responses=[
                    "княгиня грикша пишет к ѥсифу",
                    "княгиня грикша вспоминает федосьꙗ",
                ]
            ),
            "lemmatization": FakeLlmClient(
                responses=[
                    "княгиня грикша писать к ѥсифъ",
                    "княгиня грикша вспоминать федосьꙗ",
                ]
            ),
            "entity": FakeLlmClient(
                responses=[
                    "Княгиня Грикша\tкнягиня грикша\nѤсифъ\tѥсифу",
                    "Княгиня Грикша\tкнягиня грикша\nФедосьꙗ\tфедосьꙗ",
                ]
            ),
            "semantic": FakeLlmClient(
                responses=[
                    "not stated\t\t0.2",
                    "daughter of\ttarget_to_source\t0.7",
                ]
            ),
        }

    def _run_tiny_corpus_pipeline(self) -> dict[str, object]:
        clients = self._tiny_corpus_clients()
        result: dict[str, object] = {}

        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            input_dir = Path(input_temp_dir)
            output_dir = Path(output_temp_dir)
            (input_dir / "003.003.txt").write_text(
                "Княгиня Грикша пишет к ѥсифу.",
                encoding="utf-8",
            )
            (input_dir / "004.004.txt").write_text(
                "Княгиня Грикша вспоминает Федосьꙗ.",
                encoding="utf-8",
            )

            config = AppConfig.from_mapping(
                {
                    "input_dir": input_dir,
                    "output_dir": output_dir,
                    "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                    "model_name": "local-model",
                    "enable_semantic_annotation": True,
                }
            )

            result["source_files"] = FileIngestionService().ingest(config)
            source_text_by_file = {
                source_file.filename: source_file.text
                for source_file in result["source_files"]
            }
            result["normalized_files"] = NormalizationService(
                clients["normalization"]
            ).normalize_files(result["source_files"], output_dir)
            result["lemmatized_files"] = LemmatizationService(
                clients["lemmatization"]
            ).lemmatize_files(result["normalized_files"], output_dir)
            result["candidates"] = EntityExtractionService(
                clients["entity"]
            ).extract_candidates(
                result["lemmatized_files"],
                source_text_by_file=source_text_by_file,
            )
            result["entities"] = EntityMergeService().merge_candidates(result["candidates"])
            result["edges"] = CooccurrenceService().build_edges(result["entities"])
            lemmatized_context_by_file = {
                lemmatized_file.filename: lemmatized_file.lemma_text
                for lemmatized_file in result["lemmatized_files"]
            }
            result["semantic_edges"] = SemanticRelationService(
                clients["semantic"]
            ).annotate_edges(
                result["edges"],
                lemmatized_context_by_file=lemmatized_context_by_file,
                enabled=config.enable_semantic_annotation,
                source_context_by_file=source_text_by_file,
            )
            export_result = GraphExporter().export(
                GraphBuilder().build(
                    result["entities"],
                    result["semantic_edges"],
                ).graph,
                output_dir,
            )
            result["payload"] = json.loads(
                export_result.json_path.read_text(encoding="utf-8")
            )
            result["html"] = export_result.html_path.read_text(encoding="utf-8")
            result["html_exists"] = export_result.html_path.is_file()

        return result

    def test_required_directories_exist(self) -> None:
        for path in [
            Path("app"),
            Path("app/ui"),
            Path("app/pipeline"),
            Path("app/graph"),
            Path("app/progress"),
            Path("app/services"),
            Path("tests"),
            Path("prompts"),
            Path("scripts"),
            Path("output"),
            Path("logs"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(path.is_dir())

    def test_required_files_exist(self) -> None:
        for path in [
            Path("app/__init__.py"),
            Path("app/main.py"),
            Path("app/config.py"),
            Path("app/ui/app.py"),
            Path("app/ui/shell.py"),
            Path("app/graph/build.py"),
            Path("app/graph/export.py"),
            Path("app/progress/reporting.py"),
            Path("app/pipeline/file_ingestion.py"),
            Path("app/pipeline/normalization.py"),
            Path("app/pipeline/lemmatization.py"),
            Path("app/pipeline/entities.py"),
            Path("app/pipeline/entity_merge.py"),
            Path("app/pipeline/cooccurrence.py"),
            Path("app/pipeline/semantic_relations.py"),
            Path("app/services/docker_runner.py"),
            Path("app/services/llm_client.py"),
            Path("prompts/normalization_prompt.txt"),
            Path("prompts/lemmatization_prompt.txt"),
            Path("prompts/entity_extraction_prompt.txt"),
            Path("prompts/semantic_relation_prompt.txt"),
            Path("requirements.txt"),
            Path("pyproject.toml"),
            Path("RUNBOOK.md"),
            Path("Dockerfile"),
            Path(".dockerignore"),
            Path("output/.gitkeep"),
            Path("logs/.gitkeep"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_config_from_mapping_returns_valid_config(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "input-data",
                "output_dir": Path("output-data"),
                "lmstudio_base_url": "http://localhost:1234/v1",
                "model_name": "local-model",
                "enable_semantic_annotation": "false",
                "enable_debug_logging": True,
            }
        )

        self.assertEqual(config.input_dir, Path("input-data"))
        self.assertEqual(config.output_dir, Path("output-data"))
        self.assertEqual(config.lmstudio_base_url, "http://localhost:1234/v1")
        self.assertEqual(config.model_name, "local-model")
        self.assertFalse(config.enable_semantic_annotation)
        self.assertTrue(config.enable_debug_logging)

    def test_config_from_env_uses_expected_variable_names(self) -> None:
        config = AppConfig.from_env(
            {
                "NETWORK_MVP_INPUT_DIR": "corpus",
                "NETWORK_MVP_OUTPUT_DIR": "artifacts",
                "NETWORK_MVP_LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
                "NETWORK_MVP_MODEL_NAME": "lmstudio-model",
                "NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION": "yes",
                "NETWORK_MVP_ENABLE_DEBUG_LOGGING": "on",
            }
        )

        self.assertEqual(config.input_dir, Path("corpus"))
        self.assertEqual(config.output_dir, Path("artifacts"))
        self.assertEqual(config.lmstudio_base_url, "http://127.0.0.1:1234/v1")
        self.assertEqual(config.model_name, "lmstudio-model")
        self.assertTrue(config.enable_semantic_annotation)
        self.assertTrue(config.enable_debug_logging)

    def test_config_missing_required_values_raise_clear_error(self) -> None:
        with self.assertRaisesRegex(
            ConfigError,
            "Missing required configuration value: input_dir",
        ):
            AppConfig.from_mapping(
                {
                    "output_dir": "output",
                    "lmstudio_base_url": "http://localhost:1234/v1",
                    "model_name": "local-model",
                }
            )

    def test_config_invalid_boolean_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(
            ConfigError,
            "Invalid boolean configuration value for enable_debug_logging",
        ):
            AppConfig.from_mapping(
                {
                    "input_dir": "input",
                    "output_dir": "output",
                    "lmstudio_base_url": "http://localhost:1234/v1",
                    "model_name": "local-model",
                    "enable_debug_logging": "maybe",
                }
            )

    def test_config_from_mapping_uses_default_flags(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "input-data",
                "output_dir": "output-data",
                "lmstudio_base_url": "http://localhost:1234/v1",
                "model_name": "local-model",
            }
        )

        self.assertTrue(config.enable_semantic_annotation)
        self.assertFalse(config.enable_debug_logging)

    def test_file_ingestion_discovers_only_txt_files(self) -> None:
        service = FileIngestionService()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.txt").write_text("A", encoding="utf-8")
            (root / "b.md").write_text("B", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "c.txt").write_text("C", encoding="utf-8")

            paths = service.discover_text_files(root)

        self.assertEqual([path.name for path in paths], ["a.txt", "c.txt"])

    def test_file_ingestion_loads_source_files_with_stable_ids(self) -> None:
        service = FileIngestionService()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "b.txt").write_text("Beta", encoding="utf-8")
            (root / "a.txt").write_text("Alpha", encoding="utf-8")

            source_files = service.load_source_files(root)

        self.assertEqual([file.file_id for file in source_files], ["text_0001", "text_0002"])
        self.assertEqual([file.filename for file in source_files], ["a.txt", "b.txt"])
        self.assertEqual([file.text for file in source_files], ["Alpha", "Beta"])
        self.assertTrue(all(isinstance(file, SourceFile) for file in source_files))

    def test_file_ingestion_exports_original_logs(self) -> None:
        service = FileIngestionService()
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="letter.txt",
                source_path=Path("/tmp/letter.txt"),
                text="Original text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            log_dir = service.export_original_logs(source_files, output_dir)
            log_path = log_dir / "text_0001_letter.txt"

            self.assertEqual(log_dir, output_dir / "logs" / "original")
            self.assertTrue(log_path.is_file())
            self.assertEqual(log_path.read_text(encoding="utf-8"), "Original text")

    def test_file_ingestion_ingest_writes_logs_outside_container_mount(self) -> None:
        service = FileIngestionService()
        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            input_dir = Path(input_temp_dir)
            output_dir = Path(output_temp_dir)
            (input_dir / "letter.txt").write_text("Text body", encoding="utf-8")
            config = AppConfig.from_mapping(
                {
                    "input_dir": input_dir,
                    "output_dir": output_dir,
                    "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                    "model_name": "local-model",
                }
            )

            source_files = service.ingest(config)

            self.assertEqual(len(source_files), 1)
            self.assertTrue(
                (output_dir / "logs" / "original" / "text_0001_letter.txt").is_file()
            )

    def test_normalization_removes_line_breaks_and_writes_output(self) -> None:
        client = FakeLlmClient(responses=["first line\nsecond line"])
        service = NormalizationService(client)
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="letter.txt",
                source_path=Path("/tmp/letter.txt"),
                text="raw text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            normalized_files = service.normalize_files(source_files, output_dir)
            output_path = output_dir / "normalized" / "text_0001_letter.txt"

            self.assertEqual(len(normalized_files), 1)
            self.assertIsInstance(normalized_files[0], NormalizedFile)
            self.assertEqual(normalized_files[0].normalized_text, "first line second line")
            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "first line second line")

    def test_normalization_writes_log_for_empty_output(self) -> None:
        client = FakeLlmClient(responses=["   "])
        service = NormalizationService(client)
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="letter.txt",
                source_path=Path("/tmp/letter.txt"),
                text="raw text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            normalized_files = service.normalize_files(source_files, output_dir)
            log_path = output_dir / "logs" / "normalization" / "text_0001_letter.txt.log"

            self.assertEqual(normalized_files, [])
            self.assertTrue(log_path.is_file())
            self.assertIn("empty normalization output", log_path.read_text(encoding="utf-8"))

    def test_normalization_raises_for_first_llm_error_and_writes_detailed_log(self) -> None:
        client = FakeLlmClient(error=LlmClientError("request failed"))
        service = NormalizationService(client)
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="letter.txt",
                source_path=Path("/tmp/letter.txt"),
                text="raw text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            log_path = output_dir / "logs" / "normalization" / "text_0001_letter.txt.log"

            with self.assertRaises(NormalizationStageError) as error_context:
                service.normalize_files(source_files, output_dir)

            self.assertTrue(log_path.is_file())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("error_type: LlmClientError", log_text)
            self.assertIn("error_message: request failed", log_text)
            self.assertIn("source_text:\nraw text", log_text)
            self.assertIn("prompt:", log_text)
            self.assertIn("See log:", str(error_context.exception))

    def test_normalization_with_zenodo_birchbark_fixtures(self) -> None:
        fixture_dir = Path("tests/fixtures/zenodo_birchbark")
        source_files = FileIngestionService().load_source_files(fixture_dir)
        client = FakeLlmClient(
            responses=[
                "поклонъ ѿ грикши къ ѥсифу\n приславъ ꙩнаньꙗ молви♮ ꙗзъ ѥму ѿвѣчалъ",
                "ѿ микит·ѣ · ко цертѹ ·\n цто ѥсм·ь · ♮руцилъ · ѹ петра",
                "♮но ѿ давꙑ♮ ♮есиѳа ·\n къ матѳѣю · постои · за нашего сироту ·",
            ]
        )
        service = NormalizationService(client)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            normalized_files = service.normalize_files(source_files, output_dir)

            self.assertEqual(
                [file.file_id for file in normalized_files],
                ["text_0001", "text_0002", "text_0003"],
            )
            self.assertEqual(
                [file.filename for file in normalized_files],
                ["003.003.txt", "004.004.txt", "005.005.txt"],
            )
            self.assertEqual(
                [file.normalized_text for file in normalized_files],
                [
                    "поклонъ ѿ грикши къ ѥсифу приславъ ꙩнаньꙗ молви♮ ꙗзъ ѥму ѿвѣчалъ",
                    "ѿ микит·ѣ · ко цертѹ · цто ѥсм·ь · ♮руцилъ · ѹ петра",
                    "♮но ѿ давꙑ♮ ♮есиѳа · къ матѳѣю · постои · за нашего сироту ·",
                ],
            )
            self.assertTrue(
                (output_dir / "normalized" / "text_0001_003.003.txt").is_file()
            )
            self.assertTrue(
                (output_dir / "normalized" / "text_0002_004.004.txt").is_file()
            )
            self.assertTrue(
                (output_dir / "normalized" / "text_0003_005.005.txt").is_file()
            )
            self.assertIn("поклонъ ѿ грикши", client.prompts[0])

    def test_lemmatization_writes_output(self) -> None:
        client = FakeLlmClient(responses=["поклонъ грикша къ ѥсифъ"])
        service = LemmatizationService(client)
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="letter.txt",
                normalized_text="поклонъ грикши къ ѥсифу",
                output_path=Path("/tmp/text_0001_letter.txt"),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lemmatized_files = service.lemmatize_files(normalized_files, output_dir)
            output_path = output_dir / "lemmas" / "text_0001_letter.txt"

            self.assertEqual(len(lemmatized_files), 1)
            self.assertIsInstance(lemmatized_files[0], LemmatizedFile)
            self.assertEqual(lemmatized_files[0].lemma_text, "поклонъ грикша къ ѥсифъ")
            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "поклонъ грикша къ ѥсифъ")

    def test_lemmatization_writes_log_for_empty_output(self) -> None:
        client = FakeLlmClient(responses=["   "])
        service = LemmatizationService(client)
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="letter.txt",
                normalized_text="поклонъ грикши къ ѥсифу",
                output_path=Path("/tmp/text_0001_letter.txt"),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lemmatized_files = service.lemmatize_files(normalized_files, output_dir)
            log_path = output_dir / "logs" / "lemmatization" / "text_0001_letter.txt.log"

            self.assertEqual(lemmatized_files, [])
            self.assertTrue(log_path.is_file())
            self.assertIn("empty lemmatization output", log_path.read_text(encoding="utf-8"))

    def test_lemmatization_writes_log_for_llm_error(self) -> None:
        client = FakeLlmClient(error=LlmClientError("request failed"))
        service = LemmatizationService(client)
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="letter.txt",
                normalized_text="поклонъ грикши къ ѥсифу",
                output_path=Path("/tmp/text_0001_letter.txt"),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lemmatized_files = service.lemmatize_files(normalized_files, output_dir)
            log_path = output_dir / "logs" / "lemmatization" / "text_0001_letter.txt.log"

            self.assertEqual(lemmatized_files, [])
            self.assertTrue(log_path.is_file())
            self.assertIn("request failed", log_path.read_text(encoding="utf-8"))

    def test_lemmatization_with_zenodo_birchbark_fixtures(self) -> None:
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                normalized_text="поклонъ ѿ грикши къ ѥсифу приславъ ꙩнаньꙗ молви♮ ꙗзъ ѥму ѿвѣчалъ",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            ),
            NormalizedFile(
                file_id="text_0002",
                filename="004.004.txt",
                normalized_text="ѿ микит·ѣ · ко цертѹ · цто ѥсм·ь · ♮руцилъ · ѹ петра",
                output_path=Path("/tmp/text_0002_004.004.txt"),
            ),
            NormalizedFile(
                file_id="text_0003",
                filename="005.005.txt",
                normalized_text="♮но ѿ давꙑ♮ ♮есиѳа · къ матѳѣю · постои · за нашего сироту ·",
                output_path=Path("/tmp/text_0003_005.005.txt"),
            ),
        ]
        client = FakeLlmClient(
            responses=[
                "поклонъ ѿ грикша къ ѥсифъ\n прислати ꙩнаньꙗ молвити ꙗзъ ѥмоу ѿвѣчати",
                "ѿ микита · ко цертъ ·\n что ѥсмь · ручити · ѹ петръ",
                "но ѿ давы ♮есиѳа ·\n къ матѳѣи · постоѧти · за нашь сирота ·",
            ]
        )
        service = LemmatizationService(client)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lemmatized_files = service.lemmatize_files(normalized_files, output_dir)

            self.assertEqual(
                [file.file_id for file in lemmatized_files],
                ["text_0001", "text_0002", "text_0003"],
            )
            self.assertEqual(
                [file.filename for file in lemmatized_files],
                ["003.003.txt", "004.004.txt", "005.005.txt"],
            )
            self.assertEqual(
                [file.lemma_text for file in lemmatized_files],
                [
                    "поклонъ ѿ грикша къ ѥсифъ прислати ꙩнаньꙗ молвити ꙗзъ ѥмоу ѿвѣчати",
                    "ѿ микита · ко цертъ · что ѥсмь · ручити · ѹ петръ",
                    "но ѿ давы ♮есиѳа · къ матѳѣи · постоѧти · за нашь сирота ·",
                ],
            )
            self.assertTrue(
                (output_dir / "lemmas" / "text_0001_003.003.txt").is_file()
            )
            self.assertTrue(
                (output_dir / "lemmas" / "text_0002_004.004.txt").is_file()
            )
            self.assertTrue(
                (output_dir / "lemmas" / "text_0003_005.005.txt").is_file()
            )
            self.assertIn("поклонъ ѿ грикши", client.prompts[0])

    def test_entity_extraction_parses_candidates_per_file(self) -> None:
        lemmatized_files = [
            LemmatizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                lemma_text="поклонъ ѿ грикша къ ѥсифъ",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            )
        ]
        client = FakeLlmClient(responses=["грикша\tгрикши\nѥсифъ\tѥсифу"])
        service = EntityExtractionService(client)

        candidates = service.extract_candidates(
            lemmatized_files,
            source_text_by_file={"003.003.txt": "поклонъ ѿ грикши къ ѥсифу"},
        )

        self.assertEqual(len(candidates), 2)
        self.assertTrue(
            all(isinstance(candidate, CandidateEntity) for candidate in candidates)
        )
        self.assertEqual(
            [candidate.file_id for candidate in candidates],
            ["text_0001", "text_0001"],
        )
        self.assertEqual(
            [candidate.filename for candidate in candidates],
            ["003.003.txt", "003.003.txt"],
        )
        self.assertEqual([candidate.name for candidate in candidates], ["грикша", "ѥсифъ"])
        self.assertEqual([candidate.evidence for candidate in candidates], ["грикши", "ѥсифу"])
        self.assertIn("поклонъ ѿ грикша", client.prompts[0])
        self.assertIn("поклонъ ѿ грикши", client.prompts[0])

    def test_entity_extraction_defaults_evidence_to_name(self) -> None:
        lemmatized_files = [
            LemmatizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                lemma_text="поклонъ ѿ грикша",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            )
        ]
        client = FakeLlmClient(responses=["грикша"])
        service = EntityExtractionService(client)

        candidates = service.extract_candidates(lemmatized_files)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].name, "грикша")
        self.assertEqual(candidates[0].evidence, "грикша")

    def test_entity_extraction_skips_llm_failure(self) -> None:
        lemmatized_files = [
            LemmatizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                lemma_text="поклонъ ѿ грикша",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            )
        ]
        client = FakeLlmClient(error=LlmClientError("request failed"))
        service = EntityExtractionService(client)

        candidates = service.extract_candidates(lemmatized_files)

        self.assertEqual(candidates, [])

    def test_entity_extraction_with_zenodo_birchbark_fixture(self) -> None:
        lemmatized_files = [
            LemmatizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                lemma_text="поклонъ ѿ грикша къ ѥсифъ къ федосьꙗ",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            )
        ]
        client = FakeLlmClient(responses=["грикша\tгрикши\nѥсифъ\tѥсифу\nфедосьꙗ\tфедосьӏ"])
        service = EntityExtractionService(client)

        candidates = service.extract_candidates(lemmatized_files)

        self.assertEqual(
            [candidate.name for candidate in candidates],
            ["грикша", "ѥсифъ", "федосьꙗ"],
        )
        self.assertEqual(
            [candidate.evidence for candidate in candidates],
            ["грикши", "ѥсифу", "федосьӏ"],
        )
        self.assertEqual(
            [candidate.filename for candidate in candidates],
            ["003.003.txt", "003.003.txt", "003.003.txt"],
        )

    def test_entity_merge_groups_aliases_and_source_files(self) -> None:
        candidates = [
            CandidateEntity(
                file_id="text_0001",
                filename="003.003.txt",
                name="Грикша",
                evidence="грикши",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="004.004.txt",
                name="грикша",
                evidence="грикша",
            ),
            CandidateEntity(
                file_id="text_0003",
                filename="005.005.txt",
                name="Ѥсифъ",
                evidence="ѥсифу",
            ),
        ]
        merged = EntityMergeService().merge_candidates(candidates)

        self.assertEqual(len(merged), 2)
        self.assertTrue(all(isinstance(entity, CanonicalEntity) for entity in merged))
        self.assertEqual(merged[0].canonical_name, "грикша")
        self.assertEqual(merged[0].aliases, ("Грикша", "грикша"))
        self.assertEqual(merged[0].source_files, ("003.003.txt", "004.004.txt"))
        self.assertEqual(merged[0].evidence, ("грикша", "грикши"))

    def test_entity_merge_strips_supported_titles(self) -> None:
        candidates = [
            CandidateEntity(
                file_id="text_0001",
                filename="001.txt",
                name="княгиня Ольга",
                evidence="княгиня ольга",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="002.txt",
                name="Ольга",
                evidence="ольга",
            ),
        ]
        merged = EntityMergeService().merge_candidates(candidates)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].canonical_name, "ольга")
        self.assertEqual(merged[0].aliases, ("Ольга", "княгиня Ольга"))

    def test_entity_merge_infers_gender_when_possible(self) -> None:
        candidates = [
            CandidateEntity(
                file_id="text_0001",
                filename="001.txt",
                name="N",
                evidence="n",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="002.txt",
                name="Ольга",
                evidence="ольга",
            ),
            CandidateEntity(
                file_id="text_0003",
                filename="003.txt",
                name="Ѥсифъ",
                evidence="ѥсифу",
            ),
        ]
        merged = EntityMergeService().merge_candidates(candidates)

        self.assertEqual(merged[0].gender_inference, "unresolved")
        self.assertEqual(merged[1].gender_inference, "female")
        self.assertEqual(merged[2].gender_inference, "not-inferred")

    def test_entity_merge_marks_ambiguous_gender_on_conflicting_signals(self) -> None:
        merged = EntityMergeService().merge_candidates(
            [
                CandidateEntity(
                    file_id="text_0001",
                    filename="001.txt",
                    name="N",
                    evidence="n",
                ),
                CandidateEntity(
                    file_id="text_0002",
                    filename="002.txt",
                    name="Княгиня N",
                    evidence="княгиня n",
                ),
            ]
        )

        self.assertEqual(merged[0].gender_inference, "ambiguous")

    def test_entity_merge_with_birchbark_style_candidates(self) -> None:
        candidates = [
            CandidateEntity(
                file_id="text_0001",
                filename="003.003.txt",
                name="Грикша",
                evidence="грикши",
            ),
            CandidateEntity(
                file_id="text_0001",
                filename="003.003.txt",
                name="Ѥсифъ",
                evidence="ѥсифу",
            ),
            CandidateEntity(
                file_id="text_0001",
                filename="003.003.txt",
                name="Федосьꙗ",
                evidence="федосьӏ",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="004.004.txt",
                name="Петръ",
                evidence="петра",
            ),
            CandidateEntity(
                file_id="text_0002",
                filename="004.004.txt",
                name="Юрга",
                evidence="юрги",
            ),
            CandidateEntity(
                file_id="text_0003",
                filename="005.005.txt",
                name="княгиня Ольга",
                evidence="княгиня ольга",
            ),
            CandidateEntity(
                file_id="text_0004",
                filename="006.006.txt",
                name="Ольга",
                evidence="ольга",
            ),
        ]
        merged = EntityMergeService().merge_candidates(candidates)
        merged_by_name = {entity.canonical_name: entity for entity in merged}

        self.assertIn("грикша", merged_by_name)
        self.assertIn("ѥсифъ", merged_by_name)
        self.assertIn("федосьꙗ", merged_by_name)
        self.assertIn("петръ", merged_by_name)
        self.assertIn("юрга", merged_by_name)
        self.assertIn("ольга", merged_by_name)
        self.assertEqual(merged_by_name["грикша"].evidence, ("грикши",))
        self.assertEqual(merged_by_name["ѥсифъ"].source_files, ("003.003.txt",))
        self.assertEqual(merged_by_name["федосьꙗ"].gender_inference, "female")
        self.assertEqual(merged_by_name["ольга"].aliases, ("Ольга", "княгиня Ольга"))
        self.assertEqual(merged_by_name["ольга"].source_files, ("005.005.txt", "006.006.txt"))

    def test_cooccurrence_builds_weighted_edges(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not-inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not-inferred",
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
                gender_inference="not-inferred",
            ),
        ]
        edges = CooccurrenceService().build_edges(entities)

        self.assertTrue(all(isinstance(edge, CooccurrenceEdge) for edge in edges))
        self.assertEqual(
            [(edge.source, edge.target, edge.weight, edge.source_files) for edge in edges],
            [
                ("грикша", "петръ", 1, ("004.004.txt",)),
                ("грикша", "федосьꙗ", 1, ("003.003.txt",)),
                ("грикша", "ѥсифъ", 1, ("003.003.txt",)),
                ("федосьꙗ", "ѥсифъ", 1, ("003.003.txt",)),
            ],
        )

    def test_cooccurrence_avoids_self_loops(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша", "грикша"),
                source_files=("003.003.txt",),
                evidence=("грикши", "грикша"),
                gender_inference="not-inferred",
            )
        ]
        edges = CooccurrenceService().build_edges(entities)

        self.assertEqual(edges, [])

    def test_cooccurrence_with_birchbark_style_entities(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not-inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not-inferred",
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
                gender_inference="not-inferred",
            ),
            CanonicalEntity(
                canonical_name="юрга",
                aliases=("Юрга",),
                source_files=("004.004.txt",),
                evidence=("юрги",),
                gender_inference="female",
            ),
        ]
        edges = CooccurrenceService().build_edges(entities)
        edge_map = {(edge.source, edge.target): edge for edge in edges}

        self.assertEqual(edge_map[("грикша", "петръ")].source_files, ("004.004.txt",))
        self.assertEqual(edge_map[("грикша", "юрга")].source_files, ("004.004.txt",))
        self.assertEqual(edge_map[("грикша", "ѥсифъ")].source_files, ("003.003.txt",))
        self.assertEqual(edge_map[("федосьꙗ", "ѥсифъ")].weight, 1)
        self.assertEqual(edge_map[("петръ", "юрга")].weight, 1)

    def test_semantic_relation_annotation_disabled_keeps_plain_edges(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            )
        ]
        service = SemanticRelationService(FakeLlmClient())

        annotated = service.annotate_edges(edges, lemmatized_context_by_file={}, enabled=False)

        self.assertEqual(len(annotated), 1)
        self.assertIsInstance(annotated[0], SemanticEdge)
        self.assertEqual(annotated[0].semantic_relation, None)
        self.assertEqual(annotated[0].semantic_confidence, None)

    def test_semantic_relation_annotation_parses_allowed_label(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="княгиня ольга",
                target="игорь",
                weight=1,
                source_files=("001.txt",),
            )
        ]
        client = FakeLlmClient(responses=["wife of\tsource_to_target\t0.8"])
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={"001.txt": "ольга и игорь"},
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "wife of")
        self.assertEqual(annotated[0].semantic_direction, "source_to_target")
        self.assertEqual(annotated[0].semantic_confidence, 0.8)

    def test_semantic_relation_annotation_maps_unknown_label_to_not_stated(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            )
        ]
        client = FakeLlmClient(responses=["ally of\tsource_to_target\t0.7"])
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={"003.003.txt": "грикша и ѥсифъ"},
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "not stated")
        self.assertEqual(annotated[0].semantic_confidence, 0.0)

    def test_semantic_relation_annotation_falls_back_on_error(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            )
        ]
        client = FakeLlmClient(error=LlmClientError("request failed"))
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={"003.003.txt": "грикша и ѥсифъ"},
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "not stated")
        self.assertEqual(annotated[0].semantic_confidence, 0.0)

    def test_semantic_relation_with_birchbark_style_context(self) -> None:
        edges = [
            CooccurrenceEdge(
                source="грикша",
                target="ѥсифъ",
                weight=1,
                source_files=("003.003.txt",),
            ),
            CooccurrenceEdge(
                source="ѥсифъ",
                target="федосьꙗ",
                weight=1,
                source_files=("003.003.txt",),
            ),
        ]
        client = FakeLlmClient(
            responses=[
                "not stated\t\t0.3",
                "daughter of\ttarget_to_source\t0.6",
            ]
        )
        service = SemanticRelationService(client)

        annotated = service.annotate_edges(
            edges,
            lemmatized_context_by_file={
                "003.003.txt": "поклонъ ѿ грикша къ ѥсифъ ... къ федосьꙗ ...",
            },
            enabled=True,
        )

        self.assertEqual(annotated[0].semantic_relation, "not stated")
        self.assertEqual(annotated[1].semantic_relation, "daughter of")
        self.assertEqual(annotated[1].semantic_direction, "target_to_source")
        self.assertEqual(annotated[1].semantic_confidence, 0.6)
        self.assertIn("Entity A: грикша", client.prompts[0])
        self.assertIn("Entity B: ѥсифъ", client.prompts[0])

    def test_graph_builder_constructs_graph_and_centrality(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not-inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not-inferred",
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
                gender_inference="not-inferred",
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
                gender_inference="not-inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not-inferred",
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
                gender_inference="not-inferred",
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
                gender_inference="not-inferred",
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
        self.assertIn('федосьꙗ', graph_json)
        self.assertIn('<html', graph_html.lower())

    def test_graph_export_with_realistic_semantic_graph(self) -> None:
        entities = [
            CanonicalEntity(
                canonical_name="грикша",
                aliases=("Грикша",),
                source_files=("003.003.txt", "004.004.txt"),
                evidence=("грикши",),
                gender_inference="not-inferred",
            ),
            CanonicalEntity(
                canonical_name="ѥсифъ",
                aliases=("Ѥсифъ",),
                source_files=("003.003.txt",),
                evidence=("ѥсифу",),
                gender_inference="not-inferred",
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
        self.assertTrue("daughter of" in html or "graph-data" in html)
        self.assertTrue("003.003.txt" in html or "graph-data" in html)

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
                gender_inference="not-inferred",
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

    def test_docker_runner_builds_expected_command(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
                "enable_semantic_annotation": True,
                "enable_debug_logging": False,
            }
        )

        command = DockerRunner(image_name="network-mvp:test").build_command(config)

        self.assertEqual(command[0:3], ["docker", "run", "--rm"])
        self.assertIn("NETWORK_MVP_INPUT_DIR=/data/input", command)
        self.assertIn("NETWORK_MVP_OUTPUT_DIR=/data/output", command)
        self.assertIn("NETWORK_MVP_LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1", command)
        self.assertIn("NETWORK_MVP_MODEL_NAME=local-model", command)
        self.assertIn("NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION=true", command)
        self.assertIn("NETWORK_MVP_ENABLE_DEBUG_LOGGING=false", command)
        self.assertIn("network-mvp:test", command)

    def test_docker_runner_builds_image_before_run(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            }
        )
        runner = DockerRunner(image_name="network-mvp:test")

        with mock.patch("app.services.docker_runner.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess(
                    ["docker", "build", "-t", "network-mvp:test", "."],
                    0,
                    stdout="built",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    ["docker", "run"],
                    0,
                    stdout="ok",
                    stderr="",
                ),
            ]

            result = runner.run(config)

        self.assertTrue(result.succeeded)
        self.assertEqual(mock_run.call_args_list[0].kwargs["cwd"], runner.project_root)
        self.assertEqual(
            mock_run.call_args_list[0].args[0],
            ["docker", "build", "-t", "network-mvp:test", "."],
        )

    def test_docker_runner_returns_build_failure_when_image_build_fails(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            }
        )
        runner = DockerRunner(image_name="network-mvp:test")

        with mock.patch("app.services.docker_runner.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess(
                    ["docker", "build", "-t", "network-mvp:test", "."],
                    1,
                    stdout="",
                    stderr="build failed",
                ),
            ]

            result = runner.run(config)

        self.assertFalse(result.succeeded)
        self.assertEqual(result.command, ["docker", "build", "-t", "network-mvp:test", "."])
        self.assertEqual(result.stderr, "build failed")

    def test_llm_client_uses_config_values(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            }
        )
        completions = FakeCompletions(response=FakeResponse("hello"))
        factory_calls: list[dict[str, object]] = []

        def client_factory(*, base_url: str, timeout: float) -> FakeClient:
            factory_calls.append({"base_url": base_url, "timeout": timeout})
            return FakeClient(completions)

        client = LlmClient.from_config(config, timeout=12.5, client_factory=client_factory)
        response = client.prompt("ping")

        self.assertIsInstance(response, LlmResponse)
        self.assertEqual(response.text, "hello")
        self.assertEqual(factory_calls, [{"base_url": "http://127.0.0.1:1234/v1", "timeout": 12.5}])
        self.assertEqual(completions.calls[0]["model"], "local-model")

    def test_llm_client_default_factory_supplies_lm_studio_api_key(self) -> None:
        fake_openai_class = mock.Mock(return_value=object())
        fake_openai_module = type("FakeOpenAiModule", (), {"OpenAI": fake_openai_class})()

        with (
            mock.patch(
                "app.services.llm_client.importlib.import_module",
                return_value=fake_openai_module,
            ),
            mock.patch.dict(llm_client_module.os.environ, {}, clear=True),
        ):
            client = LlmClient(
                base_url="http://127.0.0.1:1234/v1",
                model_name="local-model",
            )

        self.assertIsInstance(client, LlmClient)
        fake_openai_class.assert_called_once_with(
            base_url="http://127.0.0.1:1234/v1",
            timeout=60.0,
            api_key="lm-studio",
        )

    def test_llm_client_builds_messages_and_extracts_text(self) -> None:
        completions = FakeCompletions(response=FakeResponse(" answer text "))
        client = LlmClient(
            base_url="http://127.0.0.1:1234/v1",
            model_name="local-model",
            client_factory=lambda **_: FakeClient(completions),
        )

        response = client.prompt("user prompt", system_prompt="system prompt")

        self.assertEqual(response.text, "answer text")
        self.assertEqual(
            completions.calls[0]["messages"],
            [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
        )

    def test_llm_client_rejects_empty_prompt(self) -> None:
        client = LlmClient(
            base_url="http://127.0.0.1:1234/v1",
            model_name="local-model",
            client_factory=lambda **_: FakeClient(FakeCompletions(response=FakeResponse("ok"))),
        )

        with self.assertRaisesRegex(LlmClientError, "Prompt text must not be empty"):
            client.prompt("   ")

    def test_llm_client_surfaces_request_error(self) -> None:
        client = LlmClient(
            base_url="http://127.0.0.1:1234/v1",
            model_name="local-model",
            client_factory=lambda **_: FakeClient(
                FakeCompletions(error=RuntimeError("connection refused"))
            ),
        )

        with self.assertRaisesRegex(LlmClientError, "LLM request failed: connection refused"):
            client.prompt("ping")

    def test_llm_client_surfaces_missing_content_error(self) -> None:
        client = LlmClient(
            base_url="http://127.0.0.1:1234/v1",
            model_name="local-model",
            client_factory=lambda **_: FakeClient(FakeCompletions(response=FakeResponse(None))),
        )

        with self.assertRaisesRegex(
            LlmClientError,
            "LLM response did not contain message content",
        ):
            client.prompt("ping")

    def test_ui_defaults_include_required_input_fields(self) -> None:
        defaults = default_form_values()

        self.assertIsInstance(defaults, UiDefaults)
        self.assertEqual(defaults.input_dir, "")
        self.assertEqual(defaults.output_dir, "./output")
        self.assertEqual(defaults.lmstudio_base_url, "http://127.0.0.1:1234/v1")
        self.assertEqual(defaults.model_name, "")

    def test_ui_run_handler_accepts_valid_inputs(self) -> None:
        runner = FakeRunner(
            DockerRunResult(
                command=["docker", "run"],
                returncode=0,
                stdout="ok",
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

        self.assertIsInstance(response, UiRunResponse)
        self.assertIsInstance(response.config, AppConfig)
        self.assertEqual(response.status_message, "Container run completed successfully.")
        self.assertEqual(response.result, runner.result)
        self.assertIsNotNone(runner.received_config)
        self.assertIsNotNone(response.progress_state)
        progress_state = response.progress_state
        if progress_state is None:
            self.fail("expected progress state")
        self.assertEqual(progress_state.current_stage, "completed")

    def test_ui_run_handler_returns_clear_error_for_invalid_inputs(self) -> None:
        response = handle_run_request(
            {
                "input_dir": "",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            }
        )

        self.assertIsNone(response.config)
        self.assertEqual(response.status_message, "Missing required configuration value: input_dir")
        self.assertIsNone(response.result)

    def test_ui_run_handler_returns_runner_failure_message(self) -> None:
        runner = FakeRunner(
            DockerRunResult(
                command=["docker", "run"],
                returncode=1,
                stdout="",
                stderr="boom",
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

        self.assertEqual(response.status_message, "Container run failed: boom")
        self.assertEqual(response.result, runner.result)
        self.assertIsNotNone(response.progress_state)
        progress_state = response.progress_state
        if progress_state is None:
            self.fail("expected progress state")
        self.assertEqual(progress_state.status, "failed")

    def test_main_entrypoint_runs_pipeline_and_reports_progress(self) -> None:
        fake_client = FakeLlmClient(
            responses=[
                "княгиня грикша пишет к ѥсифу",
                "княгиня грикша писать к ѥсифъ",
                "Княгиня Грикша\tкнягиня грикша\nѤсифъ\tѥсифу",
                "not stated\t\t0.2",
            ]
        )

        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            input_dir = Path(input_temp_dir)
            output_dir = Path(output_temp_dir)
            (input_dir / "003.003.txt").write_text(
                "Княгиня Грикша пишет к ѥсифу.",
                encoding="utf-8",
            )

            buffer = io.StringIO()
            with (
                mock.patch(
                    "app.main.LlmClient.from_config",
                    return_value=fake_client,
                ),
                mock.patch.dict(
                    "os.environ",
                    {
                        "NETWORK_MVP_INPUT_DIR": str(input_dir),
                        "NETWORK_MVP_OUTPUT_DIR": str(output_dir),
                        "NETWORK_MVP_LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
                        "NETWORK_MVP_MODEL_NAME": "local-model",
                    },
                    clear=False,
                ),
                mock.patch("sys.stdout", buffer),
            ):
                app_main.main()

            stdout = buffer.getvalue()
            self.assertIn("PROGRESS\tstage=startup", stdout)
            self.assertIn("PROGRESS\tstage=ingestion\tcompleted=1\ttotal=1", stdout)
            self.assertIn("PROGRESS\tstage=graph_export\tcompleted=1\ttotal=1", stdout)
            self.assertTrue((output_dir / "graph.json").is_file())
            self.assertTrue((output_dir / "graph.html").is_file())

    def test_main_entrypoint_fails_fast_on_first_normalization_llm_error(self) -> None:
        fake_client = FakeLlmClient(error=LlmClientError("connection refused"))

        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            input_dir = Path(input_temp_dir)
            output_dir = Path(output_temp_dir)
            (input_dir / "003.003.txt").write_text(
                "Княгиня Грикша пишет к ѥсифу.",
                encoding="utf-8",
            )

            buffer = io.StringIO()
            with (
                mock.patch(
                    "app.main.LlmClient.from_config",
                    return_value=fake_client,
                ),
                mock.patch.dict(
                    "os.environ",
                    {
                        "NETWORK_MVP_INPUT_DIR": str(input_dir),
                        "NETWORK_MVP_OUTPUT_DIR": str(output_dir),
                        "NETWORK_MVP_LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
                        "NETWORK_MVP_MODEL_NAME": "local-model",
                    },
                    clear=False,
                ),
                mock.patch("sys.stdout", buffer),
            ):
                with self.assertRaises(SystemExit) as error_context:
                    app_main.main()

            stdout = buffer.getvalue()
            self.assertIn("PROGRESS\tstage=ingestion\tcompleted=1\ttotal=1", stdout)
            self.assertIn("PROGRESS\tstage=normalization\tcompleted=0\ttotal=1\tstatus=failed", stdout)
            self.assertNotIn("PROGRESS\tstage=lemmatization", stdout)
            self.assertIn("Normalization failed on first file", str(error_context.exception))
            self.assertTrue(
                (output_dir / "logs" / "normalization" / "text_0001_003.003.txt.log").is_file()
            )

    def test_runbook_documents_lm_studio_and_manual_cleanup(self) -> None:
        runbook = Path("RUNBOOK.md").read_text(encoding="utf-8")

        self.assertIn("LM Studio", runbook)
        self.assertIn("not stated", runbook)
        self.assertIn("graph.json", runbook)
        self.assertIn("graph.html", runbook)
        self.assertIn("lemmatized text", runbook)

    def test_requirements_include_core_dependencies(self) -> None:
        requirements = Path("requirements.txt").read_text(encoding="utf-8")

        for dependency in ["networkx", "pyvis", "pandas", "streamlit", "openai", "pylint", "mypy"]:
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, requirements)


if __name__ == "__main__":
    unittest.main()
