"""Shared fixtures and helpers for the focused test suites."""

# The support module deliberately re-exports common test dependencies so each
# focused suite can import only the fixtures it needs.

import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from typing import TypedDict
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
from app.pipeline.file_ingestion import (
    FileIngestionService,
    InputDirectoryError,
    SourceFile,
)
from app.pipeline.lemmatization import LemmatizationService, LemmatizedFile
from app.pipeline.normalization import (
    NormalizationService,
    NormalizedFile,
    NormalizationStageError,
)
from app.services.docker_runner import DockerRunResult, DockerRunner
from app.services.llm_client import LlmClient, LlmClientError, LlmResponse
from app.ui.shell import UiDefaults, UiRunResponse, default_form_values, handle_run_request


class TinyPipelineResult(TypedDict, total=False):
    source_files: list[SourceFile]
    normalized_files: list[NormalizedFile]
    lemmatized_files: list[LemmatizedFile]
    candidates: list[CandidateEntity]
    entities: list[CanonicalEntity]
    edges: list[CooccurrenceEdge]
    semantic_edges: list[SemanticEdge]
    payload: dict[str, list[dict[str, object]]]
    html: str
    html_exists: bool


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


class ScaffoldTestBase(unittest.TestCase):
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

    def _run_tiny_corpus_pipeline(self) -> TinyPipelineResult:
        clients = self._tiny_corpus_clients()
        result: TinyPipelineResult = {}

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
                source_text_by_file=source_text_by_file,
            )
            result["payload"] = json.loads(
                export_result.json_path.read_text(encoding="utf-8")
            )
            result["html"] = export_result.html_path.read_text(encoding="utf-8")
            result["html_exists"] = export_result.html_path.is_file()

        return result


__all__ = [
    "AppConfig",
    "CandidateEntity",
    "CanonicalEntity",
    "ConfigError",
    "CooccurrenceEdge",
    "CooccurrenceService",
    "DockerRunResult",
    "DockerRunner",
    "EntityExtractionService",
    "EntityMergeService",
    "FakeChoice",
    "FakeClient",
    "FakeCompletions",
    "FakeLlmClient",
    "FakeMessage",
    "FakeResponse",
    "FakeRunner",
    "FileIngestionService",
    "GraphBuildResult",
    "GraphBuilder",
    "GraphExportResult",
    "GraphExporter",
    "InputDirectoryError",
    "LemmatizationService",
    "LemmatizedFile",
    "LlmClient",
    "LlmClientError",
    "LlmResponse",
    "NormalizationService",
    "NormalizationStageError",
    "NormalizedFile",
    "Path",
    "ProgressReporter",
    "ProgressState",
    "ScaffoldTestBase",
    "SemanticEdge",
    "SemanticRelationService",
    "SourceFile",
    "TinyPipelineResult",
    "TypedDict",
    "UiDefaults",
    "UiRunResponse",
    "app_main",
    "default_form_values",
    "handle_run_request",
    "io",
    "json",
    "llm_client_module",
    "mock",
    "subprocess",
    "tempfile",
    "unittest",
]
