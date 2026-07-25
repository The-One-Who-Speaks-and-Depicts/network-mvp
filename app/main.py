"""Application entrypoint."""

from __future__ import annotations

from app.config import AppConfig
from app.graph.build import GraphBuilder
from app.graph.export import GraphExporter
from app.pipeline.cooccurrence import CooccurrenceService
from app.pipeline.entities import EntityExtractionService
from app.pipeline.entity_merge import EntityMergeService
from app.pipeline.file_ingestion import FileIngestionService
from app.pipeline.lemmatization import LemmatizationService
from app.pipeline.normalization import NormalizationService, NormalizationStageError
from app.pipeline.semantic_relations import SemanticRelationService
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
        f"status={status}\tmessage={message}"
    )


def main() -> None:
    config = AppConfig.from_env()
    llm_client = LlmClient.from_config(config)

    _emit_progress(
        stage="startup",
        completed=0,
        total=0,
        status="running",
        message="Container started",
    )

    source_files = FileIngestionService().ingest(config)
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
        status="completed",
        message="Normalization finished",
    )

    lemmatized_files = LemmatizationService(llm_client).lemmatize_files(
        normalized_files,
        config.output_dir,
    )
    _emit_progress(
        stage="lemmatization",
        completed=len(lemmatized_files),
        total=total_files,
        status="completed",
        message="Lemmatization finished",
    )

    source_text_by_file = {
        source_file.filename: source_file.text
        for source_file in source_files
    }
    candidates = EntityExtractionService(llm_client).extract_candidates(
        lemmatized_files,
        source_text_by_file=source_text_by_file,
    )
    _emit_progress(
        stage="entity_extraction",
        completed=len(lemmatized_files),
        total=total_files,
        status="completed",
        message=f"Extracted {len(candidates)} candidate entities",
    )

    entities = EntityMergeService().merge_candidates(candidates)
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

    graph_result = GraphBuilder().build(entities, semantic_edges)
    GraphExporter().export(
        graph_result.graph,
        config.output_dir,
        source_text_by_file=source_text_by_file,
    )
    _emit_progress(
        stage="graph_export",
        completed=total_files,
        total=total_files,
        status="completed",
        message="Artifacts exported",
    )


if __name__ == "__main__":
    main()
