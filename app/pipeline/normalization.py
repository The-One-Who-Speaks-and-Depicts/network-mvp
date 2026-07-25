"""Normalization stage for source texts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import traceback

from app.pipeline.file_ingestion import SourceFile
from app.services.llm_client import LlmClientError, PromptingClient


@dataclass(frozen=True)
class NormalizedFile:
    file_id: str
    filename: str
    normalized_text: str
    output_path: Path


class NormalizationStageError(RuntimeError):
    def __init__(self, source_file: SourceFile, log_path: Path, error_message: str) -> None:
        super().__init__(
            "Normalization failed on first file "
            f"{source_file.filename}: {error_message}. See log: {log_path}"
        )
        self.source_file = source_file
        self.log_path = log_path
        self.error_message = error_message


class NormalizationService:
    def __init__(
        self,
        llm_client: PromptingClient,
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

        for index, source_file in enumerate(source_files):
            prompt = prompt_template.format(text=source_file.text)
            try:
                response = self.llm_client.prompt(prompt)
                normalized_text = self._sanitize_output(response.text)
                if not normalized_text:
                    raise ValueError("empty normalization output")
            except (LlmClientError, ValueError) as error:
                log_path = self._write_malformed_log(
                    malformed_log_dir,
                    source_file,
                    prompt=prompt,
                    error=error,
                )
                if index == 0 and isinstance(error, LlmClientError):
                    raise NormalizationStageError(source_file, log_path, str(error)) from error
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
        *,
        prompt: str,
        error: Exception,
    ) -> Path:
        log_path = log_dir / f"{source_file.file_id}_{source_file.filename}.log"
        timestamp = datetime.now(timezone.utc).isoformat()
        log_path.write_text(
            "\n".join(
                [
                    f"timestamp_utc: {timestamp}",
                    "stage: normalization",
                    f"file_id: {source_file.file_id}",
                    f"filename: {source_file.filename}",
                    f"source_path: {source_file.source_path}",
                    f"error_type: {type(error).__name__}",
                    f"error_message: {error}",
                    "traceback:",
                    "".join(traceback.format_exception(type(error), error, error.__traceback__)).rstrip(),
                    "source_text:",
                    source_file.text,
                    "prompt:",
                    prompt,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return log_path
