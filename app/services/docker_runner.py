"""Docker runner for pipeline container execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from app.config import AppConfig


@dataclass(frozen=True)
class DockerRunResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


class DockerRunner:
    def __init__(self, image_name: str = "network-mvp:test") -> None:
        self.image_name = image_name

    def build_command(self, config: AppConfig) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{config.input_dir.resolve()}:/data/input",
            "-v",
            f"{config.output_dir.resolve()}:/data/output",
            "-e",
            f"NETWORK_MVP_INPUT_DIR=/data/input",
            "-e",
            f"NETWORK_MVP_OUTPUT_DIR=/data/output",
            "-e",
            f"NETWORK_MVP_LMSTUDIO_BASE_URL={config.lmstudio_base_url}",
            "-e",
            f"NETWORK_MVP_MODEL_NAME={config.model_name}",
            "-e",
            (
                "NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION="
                f"{str(config.enable_semantic_annotation).lower()}"
            ),
            "-e",
            f"NETWORK_MVP_ENABLE_DEBUG_LOGGING={str(config.enable_debug_logging).lower()}",
            self.image_name,
        ]

    def run(self, config: AppConfig) -> DockerRunResult:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        command = self.build_command(config)
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        return DockerRunResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
