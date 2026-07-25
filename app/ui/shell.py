"""Helpers for local UI shell."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig, ConfigError
from app.progress.reporting import ProgressReporter, ProgressState
from app.services.docker_runner import DockerRunner, DockerRunResult


@dataclass(frozen=True)
class UiDefaults:
    input_dir: str = ""
    output_dir: str = "./output"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    model_name: str = ""


@dataclass(frozen=True)
class UiRunResponse:
    config: AppConfig | None
    status_message: str
    result: DockerRunResult | None = None
    progress_state: ProgressState | None = None


def default_form_values() -> UiDefaults:
    return UiDefaults()


def handle_run_request(
    form_values: dict[str, object],
    runner: DockerRunner | None = None,
) -> UiRunResponse:
    try:
        config = AppConfig.from_mapping(form_values)
    except ConfigError as error:
        return UiRunResponse(config=None, status_message=str(error))

    active_runner = runner or DockerRunner()
    result = active_runner.run(config)

    progress_state = ProgressReporter().from_result(
        stdout=result.stdout,
        stderr=result.stderr,
        succeeded=result.succeeded,
    )

    if result.succeeded:
        return UiRunResponse(
            config=config,
            status_message="Container run completed successfully.",
            result=result,
            progress_state=progress_state,
        )

    error_message = (
        progress_state.message.strip()
        or result.stderr.strip()
        or result.stdout.strip()
        or "Unknown Docker error"
    )
    return UiRunResponse(
        config=config,
        status_message=f"Container run failed: {error_message}",
        result=result,
        progress_state=progress_state,
    )
