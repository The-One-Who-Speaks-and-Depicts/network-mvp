"""Candidate entity extraction stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.pipeline.file_ingestion import SourceFile
from app.services.llm_client import LlmClient, LlmClientError


@dataclass(frozen=True)
class CandidateEntity:
    file_id: str
    filename: str
    name: str
    evidence: str


class EntityExtractionService:
    def __init__(
        self,
        llm_client: LlmClient,
        prompt_template_path: Path | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_template_path = prompt_template_path or Path("prompts/entity_extraction_prompt.txt")

    def extract_candidates(self, source_files: list[SourceFile]) -> list[CandidateEntity]:
        prompt_template = self.prompt_template_path.read_text(encoding="utf-8")
        candidates: list[CandidateEntity] = []

        for source_file in source_files:
            prompt = prompt_template.format(text=source_file.text)
            try:
                response = self.llm_client.prompt(prompt)
            except LlmClientError:
                continue

            candidates.extend(self._parse_response(source_file, response.text))

        return candidates

    def _parse_response(self, source_file: SourceFile, response_text: str) -> list[CandidateEntity]:
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
                    file_id=source_file.file_id,
                    filename=source_file.filename,
                    name=name,
                    evidence=evidence,
                )
            )

        return parsed
