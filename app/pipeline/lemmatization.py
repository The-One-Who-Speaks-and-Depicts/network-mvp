"""Lemmatization stage for normalized texts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.pipeline.normalization import NormalizedFile
from app.pipeline.text_utils import sanitize_output
from app.services.llm_client import LlmClientError, PromptingClient


@dataclass(frozen=True)
class LemmatizedFile:
    file_id: str
    filename: str
    lemma_text: str
    output_path: Path


class LemmatizationService:
    def __init__(
        self,
        llm_client: PromptingClient,
        prompt_template_path: Path | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_template_path = prompt_template_path or Path("prompts/lemmatization_prompt.txt")

    def lemmatize_files(
        self,
        normalized_files: list[NormalizedFile],
        output_dir: Path,
    ) -> list[LemmatizedFile]:
        lemma_dir = output_dir / "lemmas"
        malformed_log_dir = output_dir / "logs" / "lemmatization"
        lemma_dir.mkdir(parents=True, exist_ok=True)
        malformed_log_dir.mkdir(parents=True, exist_ok=True)

        prompt_template = self.prompt_template_path.read_text(encoding="utf-8")
        lemmatized_files: list[LemmatizedFile] = []

        for normalized_file in normalized_files:
            prompt = prompt_template.format(text=normalized_file.normalized_text)
            try:
                response = self.llm_client.prompt(prompt)
                lemma_text = sanitize_output(response.text)
                if not lemma_text:
                    raise ValueError("empty lemmatization output")
            except (LlmClientError, ValueError) as error:
                # One malformed file should be isolated; later corpus files still run.
                self._write_malformed_log(malformed_log_dir, normalized_file, str(error))
                continue

            output_path = lemma_dir / (
                f"{normalized_file.file_id}_{Path(normalized_file.filename).name}"
            )
            output_path.write_text(lemma_text, encoding="utf-8")
            lemmatized_files.append(
                LemmatizedFile(
                    file_id=normalized_file.file_id,
                    filename=normalized_file.filename,
                    lemma_text=lemma_text,
                    output_path=output_path,
                )
            )

        return lemmatized_files

    def _write_malformed_log(
        self,
        log_dir: Path,
        normalized_file: NormalizedFile,
        error_message: str,
    ) -> None:
        log_path = log_dir / f"{normalized_file.file_id}_{normalized_file.filename}.log"
        log_path.write_text(error_message, encoding="utf-8")
