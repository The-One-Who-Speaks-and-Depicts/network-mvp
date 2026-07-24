"""Configuration models for application runtime."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    input_dir: Path | None = None
    output_dir: Path | None = None
    lmstudio_base_url: str = ""
    model_name: str = ""
