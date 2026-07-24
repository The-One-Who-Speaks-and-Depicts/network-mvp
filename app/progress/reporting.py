"""Progress state parsing for UI reporting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    completed_files: int | None = None
    total_files: int | None = None
    status: str = "running"
    message: str = ""


@dataclass(frozen=True)
class ProgressState:
    current_stage: str
    completed_files: int | None
    total_files: int | None
    status: str
    message: str


class ProgressReporter:
    def from_result(self, stdout: str, stderr: str, succeeded: bool) -> ProgressState:
        events = self._parse_events(stdout)
        if events:
            final_event = events[-1]
            if not succeeded and final_event.status != "failed":
                return ProgressState(
                    current_stage=final_event.stage,
                    completed_files=final_event.completed_files,
                    total_files=final_event.total_files,
                    status="failed",
                    message=stderr.strip() or final_event.message or "Pipeline failed.",
                )
            return ProgressState(
                current_stage=final_event.stage,
                completed_files=final_event.completed_files,
                total_files=final_event.total_files,
                status=final_event.status,
                message=final_event.message,
            )

        if succeeded:
            return ProgressState(
                current_stage="completed",
                completed_files=None,
                total_files=None,
                status="completed",
                message="Pipeline completed successfully.",
            )

        return ProgressState(
            current_stage="failed",
            completed_files=None,
            total_files=None,
            status="failed",
            message=stderr.strip() or stdout.strip() or "Pipeline failed.",
        )

    def _parse_events(self, stdout: str) -> list[ProgressEvent]:
        events: list[ProgressEvent] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("PROGRESS\t"):
                continue
            fields: dict[str, str] = {}
            for part in line.split("\t")[1:]:
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                fields[key] = value
            stage = fields.get("stage")
            if not stage:
                continue
            events.append(
                ProgressEvent(
                    stage=stage,
                    completed_files=self._parse_int(fields.get("completed")),
                    total_files=self._parse_int(fields.get("total")),
                    status=fields.get("status", "running"),
                    message=fields.get("message", ""),
                )
            )
        return events

    def _parse_int(self, value: str | None) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None
