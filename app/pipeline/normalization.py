"""Normalization stage for source texts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.pipeline.file_ingestion import SourceFile
from app.services.llm_client import LlmClient, LlmClientError


@dataclass(frozen=True)
class NormalizedFile:
    file_id: str
    filename: str
    normalized_text: str
    output_path: Path


class NormalizationService:
    def __init__(
        self,
        llm_client: LlmClient,
        prompt_template_path: Path | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_template_path = prompt_template_path or Path("prompts/normalization_prompt.txt")

    def normalize_files(
        self,
        source_files: list[SourceFile],
        output_dir: Path,
    ) -> list[NormalizedFile]:
        normalized_dir = output_dir / "normalized"
        malformed_log_dir = output_dir / "logs" / "normalization"
        normalized_dir.mkdir(parents=True, exist_ok=True)
        malformed_log_dir.mkdir(parents=True, exist_ok=True)

        prompt_template = self.prompt_template_path.read_text(encoding="utf-8")
        normalized_files: list[NormalizedFile] = []

        for source_file in source_files:
            prompt = prompt_template.format(text=source_file.text)
            try:
                response = self.llm_client.prompt(prompt)
                normalized_text = self._sanitize_output(response.text)
                if not normalized_text:
                    raise ValueError("empty normalization output")
            except (LlmClientError, ValueError) as error:
                self._write_malformed_log(malformed_log_dir, source_file, str(error))
                continue

            output_path = normalized_dir / f"{source_file.file_id}_{source_file.filename}"
            output_path.write_text(normalized_text, encoding="utf-8")
            normalized_files.append(
                NormalizedFile(
                    file_id=source_file.file_id,
                    filename=source_file.filename,
                    normalized_text=normalized_text,
                    output_path=output_path,
                )
            )

        return normalized_files

    def _sanitize_output(self, text: str) -> str:
        return " ".join(text.split())

    def _write_malformed_log(
        self,
        log_dir: Path,
        source_file: SourceFile,
        error_message: str,
    ) -> None:
        log_path = log_dir / f"{source_file.file_id}_{source_file.filename}.log"
        log_path.write_text(error_message, encoding="utf-8")
