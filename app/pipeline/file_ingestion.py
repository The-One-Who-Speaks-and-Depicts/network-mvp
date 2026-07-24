"""File discovery and original-text logging."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import AppConfig


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
        text_files = self.discover_text_files(input_dir)
        return [
            SourceFile(
                file_id=self._make_file_id(index),
                filename=path.name,
                source_path=path,
                text=path.read_text(encoding="utf-8"),
            )
            for index, path in enumerate(text_files, start=1)
        ]

    def export_original_logs(
        self,
        source_files: list[SourceFile],
        output_dir: Path,
    ) -> Path:
        log_dir = output_dir / "logs" / "original"
        log_dir.mkdir(parents=True, exist_ok=True)

        for source_file in source_files:
            log_path = log_dir / f"{source_file.file_id}_{source_file.filename}"
            log_path.write_text(source_file.text, encoding="utf-8")

        return log_dir

    def ingest(self, config: AppConfig) -> list[SourceFile]:
        source_files = self.load_source_files(config.input_dir)
        self.export_original_logs(source_files, config.output_dir)
        return source_files

    def _make_file_id(self, index: int) -> str:
        return f"text_{index:04d}"
