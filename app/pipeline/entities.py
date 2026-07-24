"""Candidate entity extraction stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.pipeline.lemmatization import LemmatizedFile
from app.services.llm_client import LlmClientError, PromptingClient


@dataclass(frozen=True)
class CandidateEntity:
    file_id: str
    filename: str
    name: str
    evidence: str


class EntityExtractionService:
    def __init__(
        self,
        llm_client: PromptingClient,
        prompt_template_path: Path | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_template_path = (
            prompt_template_path or Path("prompts/entity_extraction_prompt.txt")
        )

    def extract_candidates(
        self,
        lemmatized_files: list[LemmatizedFile],
        source_text_by_file: dict[str, str] | None = None,
    ) -> list[CandidateEntity]:
        prompt_template = self.prompt_template_path.read_text(encoding="utf-8")
        candidates: list[CandidateEntity] = []
        source_text_lookup = source_text_by_file or {}

        for lemmatized_file in lemmatized_files:
            prompt = prompt_template.format(
                lemma_text=lemmatized_file.lemma_text,
                source_text=source_text_lookup.get(
                    lemmatized_file.filename,
                    lemmatized_file.lemma_text,
                ),
            )
            try:
                response = self.llm_client.prompt(prompt)
            except LlmClientError:
                continue

            candidates.extend(self._parse_response(lemmatized_file, response.text))

        return candidates

    def _parse_response(
        self,
        lemmatized_file: LemmatizedFile,
        response_text: str,
    ) -> list[CandidateEntity]:
        parsed: list[CandidateEntity] = []

        for line in response_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            parts = stripped.split("\t", maxsplit=1)
            name = parts[0].strip()
            evidence = parts[1].strip() if len(parts) > 1 else parts[0].strip()
            if not name:
                continue

            parsed.append(
                CandidateEntity(
                    file_id=lemmatized_file.file_id,
                    filename=lemmatized_file.filename,
                    name=name,
                    evidence=evidence,
                )
            )

        return parsed
