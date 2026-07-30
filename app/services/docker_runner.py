"""Docker runner for pipeline container execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from collections.abc import Callable
from urllib.parse import urlsplit, urlunsplit

from app.config import AppConfig
from app.pipeline.file_ingestion import validate_input_directory


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
        self.project_root = Path(__file__).resolve().parents[2]

    def build_command(self, config: AppConfig) -> list[str]:
        lmstudio_base_url = self._container_base_url(config.lmstudio_base_url)
        command = [
            "docker",
            "run",
            "--rm",
        ]
        if self._should_use_host_network(config.lmstudio_base_url):
            command.extend(["--network", "host"])
        elif self._needs_host_gateway(config.lmstudio_base_url):
            command.extend(["--add-host", "host.docker.internal:host-gateway"])
        command.extend(
            [
                "-v",
                f"{config.input_dir.resolve()}:/data/input",
                "-v",
                f"{config.output_dir.resolve()}:/data/output",
                "-e",
                "NETWORK_MVP_INPUT_DIR=/data/input",
                "-e",
                "NETWORK_MVP_OUTPUT_DIR=/data/output",
                "-e",
                f"NETWORK_MVP_LMSTUDIO_BASE_URL={lmstudio_base_url}",
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
        )
        return command

    def build_image_command(self) -> list[str]:
        return ["docker", "build", "-t", self.image_name, "."]

    def run(
        self,
        config: AppConfig,
        output_callback: Callable[[str], None] | None = None,
    ) -> DockerRunResult:
        input_error = validate_input_directory(config.input_dir)
        if input_error is not None:
            return DockerRunResult(
                command=[],
                returncode=1,
                stdout="",
                stderr=input_error,
            )
        config.output_dir.mkdir(parents=True, exist_ok=True)
        build_result = self._build_image()
        if build_result is not None:
            return build_result

        command = self.build_command(config)
        if output_callback is None:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            stdout, stderr = completed.stdout, completed.stderr
            returncode = completed.returncode
        else:
            stdout, stderr, returncode = self._run_streaming(command, output_callback)
        return DockerRunResult(
            command=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def _run_streaming(
        self,
        command: list[str],
        output_callback: Callable[[str], None],
    ) -> tuple[str, str, int]:
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        ) as process:
            stdout_lines: list[str] = []
            assert process.stdout is not None
            for line in process.stdout:
                stdout_lines.append(line)
                output_callback(line.rstrip("\n"))
            stderr = process.stderr.read() if process.stderr is not None else ""
            returncode = process.wait()
        return "".join(stdout_lines), stderr, returncode

    def _should_use_host_network(self, base_url: str) -> bool:
        hostname = urlsplit(base_url).hostname
        return sys.platform.startswith("linux") and hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
            "host.docker.internal",
        }

    def _needs_host_gateway(self, base_url: str) -> bool:
        hostname = urlsplit(base_url).hostname
        return not self._should_use_host_network(base_url) and hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
            "host.docker.internal",
        }

    def _container_base_url(self, base_url: str) -> str:
        parsed = urlsplit(base_url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}:
            return base_url
        target_hostname = (
            "127.0.0.1"
            if self._should_use_host_network(base_url)
            else "host.docker.internal"
        )
        netloc = parsed.netloc.replace(parsed.hostname, target_hostname, 1)
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

    def _build_image(self) -> DockerRunResult | None:
        build_command = self.build_image_command()
        build_result = subprocess.run(
            build_command,
            capture_output=True,
            text=True,
            check=False,
            cwd=self.project_root,
        )
        if build_result.returncode == 0:
            return None

        return DockerRunResult(
            command=build_command,
            returncode=build_result.returncode,
            stdout=build_result.stdout,
            stderr=build_result.stderr,
        )
