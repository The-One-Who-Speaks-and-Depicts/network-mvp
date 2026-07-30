"""File discovery and original-text logging."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import AppConfig


class InputDirectoryError(ValueError):
    """Raised when the configured corpus directory cannot be processed."""


def validate_input_directory(input_dir: Path) -> str | None:
    """Return a user-facing error when a corpus directory is not readable."""

    if not input_dir.is_dir():
        return f"Input directory does not exist or is not a directory: {input_dir}"

    text_files = sorted(path for path in input_dir.rglob("*.txt") if path.is_file())
    if not text_files:
        return f"Input directory contains no .txt files: {input_dir}"

    for text_file in text_files:
        try:
            text_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return f"Could not read UTF-8 corpus file {text_file}: {error}"
    return None


@dataclass(frozen=True)
class SourceFile:
    file_id: str
    filename: str
    source_path: Path
    text: str


class FileIngestionService:
    def discover_text_files(self, input_dir: Path) -> list[Path]:
        return sorted(path for path in input_dir.rglob("*.txt") if path.is_file())

    def load_source_files(self, input_dir: Path) -> list[SourceFile]:
        validation_error = validate_input_directory(input_dir)
        if validation_error is not None:
            raise InputDirectoryError(validation_error)
        text_files = self.discover_text_files(input_dir)
        return [
            SourceFile(
                file_id=self._make_file_id(index),
                # Basenames are not unique in a recursive corpus. Preserve
                # the relative path as the provenance/source identifier.
                filename=path.relative_to(input_dir).as_posix(),
                source_path=path,
                text=self._read_text(path),
            )
            for index, path in enumerate(text_files, start=1)
        ]

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise InputDirectoryError(
                f"Could not read UTF-8 corpus file {path}: {error}"
            ) from error

    def export_original_logs(
        self,
        source_files: list[SourceFile],
        output_dir: Path,
    ) -> Path:
        log_dir = output_dir / "logs" / "original"
        log_dir.mkdir(parents=True, exist_ok=True)

        for source_file in source_files:
            log_path = log_dir / f"{source_file.file_id}_{source_file.source_path.name}"
            log_path.write_text(source_file.text, encoding="utf-8")

        return log_dir

    def ingest(self, config: AppConfig) -> list[SourceFile]:
        source_files = self.load_source_files(config.input_dir)
        self.export_original_logs(source_files, config.output_dir)
        return source_files

    def _make_file_id(self, index: int) -> str:
        return f"text_{index:04d}"
