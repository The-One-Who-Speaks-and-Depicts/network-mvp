"""Application entrypoint."""

from __future__ import annotations

import logging
import os
import sys

from app.config import AppConfig, ConfigError
from app.graph.build import GraphBuilder
from app.graph.export import GraphExporter
from app.pipeline.cooccurrence import CooccurrenceService
from app.pipeline.entities import EntityExtractionService
from app.pipeline.entity_merge import CanonicalEntity, EntityMergeService
from app.pipeline.file_ingestion import FileIngestionService, InputDirectoryError, SourceFile
from app.pipeline.lemmatization import LemmatizationService
from app.pipeline.normalization import NormalizationService, NormalizationStageError
from app.pipeline.semantic_relations import SemanticEdge, SemanticRelationService
from app.services.llm_client import LlmClient


def _emit_progress(
    *,
    stage: str,
    completed: int,
    total: int,
    status: str,
    message: str,
) -> None:
    print(
        f"PROGRESS\tstage={stage}\tcompleted={completed}\ttotal={total}\t"
        f"status={status}\tmessage={message}",
        flush=True,
    )


def _omitted_source_filenames(
    source_files: list[SourceFile],
    extracted_file_ids: set[str],
) -> list[str]:
    return [
        source_file.filename
        for source_file in source_files
        if source_file.file_id not in extracted_file_ids
    ]


def _export_graph_and_report(
    entities: list[CanonicalEntity],
    semantic_edges: list[SemanticEdge],
    config: AppConfig,
    source_files: list[SourceFile],
    extracted_file_ids: set[str],
) -> None:
    graph_result = GraphBuilder().build(entities, semantic_edges)
    GraphExporter().export(
        graph_result.graph,
        config.output_dir,
        source_text_by_file={
            source_file.filename: source_file.text for source_file in source_files
        },
    )
    omitted_filenames = _omitted_source_filenames(source_files, extracted_file_ids)
    omission_message = (
        f"completed with omissions: omitted {len(omitted_filenames)} document(s)"
        f" ({', '.join(omitted_filenames)})"
        if omitted_filenames
        else "Artifacts exported"
    )
    _emit_progress(
        stage="graph_export",
        completed=len(extracted_file_ids),
        total=len(source_files),
        status="completed_with_omissions" if omitted_filenames else "completed",
        message=omission_message,
    )


def main() -> None:
    try:
        config = AppConfig.from_env()
    except ConfigError as error:
        runtime_keys = (
            "NETWORK_MVP_INPUT_DIR",
            "NETWORK_MVP_OUTPUT_DIR",
            "NETWORK_MVP_LMSTUDIO_BASE_URL",
            "NETWORK_MVP_MODEL_NAME",
            "NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION",
            "NETWORK_MVP_ENABLE_DEBUG_LOGGING",
        )
        if not any(key in os.environ for key in runtime_keys):
            print("Female Character Network Visualizer scaffold")
            _emit_progress(
                stage="scaffold",
                completed=0,
                total=0,
                status="completed",
                message="Scaffold run completed",
            )
            return
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(str(error)) from error

    llm_client = LlmClient.from_config(config)
    logging.basicConfig(
        level=logging.DEBUG if config.enable_debug_logging else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    _emit_progress(
        stage="startup",
        completed=0,
        total=0,
        status="running",
        message="Container started",
    )

    try:
        source_files = FileIngestionService().ingest(config)
    except InputDirectoryError as error:
        _emit_progress(
            stage="ingestion",
            completed=0,
            total=0,
            status="failed",
            message=str(error),
        )
        raise SystemExit(str(error)) from error
    total_files = len(source_files)
    _emit_progress(
        stage="ingestion",
        completed=total_files,
        total=total_files,
        status="completed",
        message=f"Discovered {total_files} source files",
    )

    try:
        normalized_files = NormalizationService(llm_client).normalize_files(
            source_files,
            config.output_dir,
        )
    except NormalizationStageError as error:
        _emit_progress(
            stage="normalization",
            completed=0,
            total=total_files,
            status="failed",
            message=str(error),
        )
        raise SystemExit(str(error)) from error
    _emit_progress(
        stage="normalization",
        completed=len(normalized_files),
        total=total_files,
        status="completed" if normalized_files else "failed",
        message=(
            f"Normalization finished; omitted {total_files - len(normalized_files)} document(s)"
            if len(normalized_files) < total_files
            else "Normalization finished"
        ),
    )
    if not normalized_files:
        raise SystemExit("Normalization produced no usable documents; aborting run.")

    lemmatized_files = LemmatizationService(llm_client).lemmatize_files(
        normalized_files,
        config.output_dir,
    )
    _emit_progress(
        stage="lemmatization",
        completed=len(lemmatized_files),
        total=total_files,
        status="completed" if lemmatized_files else "failed",
        message=(
            f"Lemmatization finished; omitted {total_files - len(lemmatized_files)} document(s)"
            if len(lemmatized_files) < total_files
            else "Lemmatization finished"
        ),
    )
    if not lemmatized_files:
        raise SystemExit("Lemmatization produced no usable documents; aborting run.")

    source_text_by_file = {
        source_file.filename: source_file.text
        for source_file in source_files
    }
    candidates = EntityExtractionService(llm_client).extract_candidates(
        lemmatized_files,
        source_text_by_file=source_text_by_file,
    )
    extracted_file_ids = {candidate.file_id for candidate in candidates}
    _emit_progress(
        stage="entity_extraction",
        completed=len(extracted_file_ids),
        total=total_files,
        status="completed" if candidates else "failed",
        message=(
            f"Extracted {len(candidates)} candidate entities; omitted "
            f"{len(lemmatized_files) - len(extracted_file_ids)} "
            "document(s)"
            if len(extracted_file_ids) < len(lemmatized_files)
            else f"Extracted {len(candidates)} candidate entities"
        ),
    )
    if not candidates:
        raise SystemExit("Entity extraction produced no usable records; aborting run.")

    entities = EntityMergeService(llm_client).merge_candidates(candidates)
    edges = CooccurrenceService().build_edges(entities)
    lemmatized_context_by_file = {
        lemmatized_file.filename: lemmatized_file.lemma_text
        for lemmatized_file in lemmatized_files
    }
    semantic_edges = SemanticRelationService(llm_client).annotate_edges(
        edges,
        lemmatized_context_by_file=lemmatized_context_by_file,
        enabled=config.enable_semantic_annotation,
        source_context_by_file=source_text_by_file,
    )
    _emit_progress(
        stage="semantic_annotation",
        completed=len(semantic_edges),
        total=len(edges),
        status="completed",
        message="Semantic annotation finished",
    )

    _export_graph_and_report(
        entities,
        semantic_edges,
        config,
        source_files,
        extracted_file_ids,
    )


if __name__ == "__main__":
    main()
