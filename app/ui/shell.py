"""Helpers for local UI shell."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig, ConfigError


@dataclass(frozen=True)
class UiDefaults:
    input_dir: str = ""
    output_dir: str = "./output"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    model_name: str = ""


def default_form_values() -> UiDefaults:
    return UiDefaults()


def handle_run_request(form_values: dict[str, object]) -> tuple[AppConfig | None, str]:
    try:
        config = AppConfig.from_mapping(form_values)
    except ConfigError as error:
        return None, str(error)

    return config, "Run requested. Pipeline execution not implemented yet."
