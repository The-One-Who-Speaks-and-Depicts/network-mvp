from pathlib import Path
import subprocess
import sys
import unittest

from app.config import AppConfig, ConfigError
from app.services.docker_runner import DockerRunResult, DockerRunner
from app.services.llm_client import LlmClient, LlmClientError, LlmResponse
from app.ui.shell import UiDefaults, UiRunResponse, default_form_values, handle_run_request


class FakeRunner:
    def __init__(self, result: DockerRunResult) -> None:
        self.result = result
        self.received_config: AppConfig | None = None

    def run(self, config: AppConfig) -> DockerRunResult:
        self.received_config = config
        return self.result


class FakeCompletions:
    def __init__(self, response: object | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = type("Chat", (), {"completions": completions})()


class FakeMessage:
    def __init__(self, content: object) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: object) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: object) -> None:
        self.choices = [FakeChoice(content)]


class ScaffoldTests(unittest.TestCase):
    def test_required_directories_exist(self) -> None:
        for path in [
            Path("app"),
            Path("app/ui"),
            Path("app/pipeline"),
            Path("app/graph"),
            Path("app/services"),
            Path("tests"),
            Path("prompts"),
            Path("scripts"),
            Path("output"),
            Path("logs"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(path.is_dir())

    def test_required_files_exist(self) -> None:
        for path in [
            Path("app/__init__.py"),
            Path("app/main.py"),
            Path("app/config.py"),
            Path("app/ui/app.py"),
            Path("app/ui/shell.py"),
            Path("app/services/docker_runner.py"),
            Path("app/services/llm_client.py"),
            Path("requirements.txt"),
            Path("Dockerfile"),
            Path(".dockerignore"),
            Path("output/.gitkeep"),
            Path("logs/.gitkeep"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_config_from_mapping_returns_valid_config(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "input-data",
                "output_dir": Path("output-data"),
                "lmstudio_base_url": "http://localhost:1234/v1",
                "model_name": "local-model",
                "enable_semantic_annotation": "false",
                "enable_debug_logging": True,
            }
        )

        self.assertEqual(config.input_dir, Path("input-data"))
        self.assertEqual(config.output_dir, Path("output-data"))
        self.assertEqual(config.lmstudio_base_url, "http://localhost:1234/v1")
        self.assertEqual(config.model_name, "local-model")
        self.assertFalse(config.enable_semantic_annotation)
        self.assertTrue(config.enable_debug_logging)

    def test_config_from_env_uses_expected_variable_names(self) -> None:
        config = AppConfig.from_env(
            {
                "NETWORK_MVP_INPUT_DIR": "corpus",
                "NETWORK_MVP_OUTPUT_DIR": "artifacts",
                "NETWORK_MVP_LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
                "NETWORK_MVP_MODEL_NAME": "lmstudio-model",
                "NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION": "yes",
                "NETWORK_MVP_ENABLE_DEBUG_LOGGING": "on",
            }
        )

        self.assertEqual(config.input_dir, Path("corpus"))
        self.assertEqual(config.output_dir, Path("artifacts"))
        self.assertEqual(config.lmstudio_base_url, "http://127.0.0.1:1234/v1")
        self.assertEqual(config.model_name, "lmstudio-model")
        self.assertTrue(config.enable_semantic_annotation)
        self.assertTrue(config.enable_debug_logging)

    def test_config_missing_required_values_raise_clear_error(self) -> None:
        with self.assertRaisesRegex(
            ConfigError,
            "Missing required configuration value: input_dir",
        ):
            AppConfig.from_mapping(
                {
                    "output_dir": "output",
                    "lmstudio_base_url": "http://localhost:1234/v1",
                    "model_name": "local-model",
                }
            )

    def test_config_invalid_boolean_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(
            ConfigError,
            "Invalid boolean configuration value for enable_debug_logging",
        ):
            AppConfig.from_mapping(
                {
                    "input_dir": "input",
                    "output_dir": "output",
                    "lmstudio_base_url": "http://localhost:1234/v1",
                    "model_name": "local-model",
                    "enable_debug_logging": "maybe",
                }
            )

    def test_docker_runner_builds_expected_command(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
                "enable_semantic_annotation": True,
                "enable_debug_logging": False,
            }
        )

        command = DockerRunner(image_name="network-mvp:test").build_command(config)

        self.assertEqual(command[0:3], ["docker", "run", "--rm"])
        self.assertIn("NETWORK_MVP_INPUT_DIR=/data/input", command)
        self.assertIn("NETWORK_MVP_OUTPUT_DIR=/data/output", command)
        self.assertIn("NETWORK_MVP_LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1", command)
        self.assertIn("NETWORK_MVP_MODEL_NAME=local-model", command)
        self.assertIn("NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION=true", command)
        self.assertIn("NETWORK_MVP_ENABLE_DEBUG_LOGGING=false", command)
        self.assertIn("network-mvp:test", command)

    def test_llm_client_uses_config_values(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            }
        )
        completions = FakeCompletions(response=FakeResponse("hello"))
        factory_calls: list[dict[str, object]] = []

        def client_factory(*, base_url: str, timeout: float) -> FakeClient:
            factory_calls.append({"base_url": base_url, "timeout": timeout})
            return FakeClient(completions)

        client = LlmClient.from_config(config, timeout=12.5, client_factory=client_factory)
        response = client.prompt("ping")

        self.assertIsInstance(response, LlmResponse)
        self.assertEqual(response.text, "hello")
        self.assertEqual(factory_calls, [{"base_url": "http://127.0.0.1:1234/v1", "timeout": 12.5}])
        self.assertEqual(completions.calls[0]["model"], "local-model")

    def test_llm_client_builds_messages_and_extracts_text(self) -> None:
        completions = FakeCompletions(response=FakeResponse(" answer text "))
        client = LlmClient(
            base_url="http://127.0.0.1:1234/v1",
            model_name="local-model",
            client_factory=lambda **_: FakeClient(completions),
        )

        response = client.prompt("user prompt", system_prompt="system prompt")

        self.assertEqual(response.text, "answer text")
        self.assertEqual(
            completions.calls[0]["messages"],
            [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
        )

    def test_llm_client_rejects_empty_prompt(self) -> None:
        client = LlmClient(
            base_url="http://127.0.0.1:1234/v1",
            model_name="local-model",
            client_factory=lambda **_: FakeClient(FakeCompletions(response=FakeResponse("ok"))),
        )

        with self.assertRaisesRegex(LlmClientError, "Prompt text must not be empty"):
            client.prompt("   ")

    def test_llm_client_surfaces_request_error(self) -> None:
        client = LlmClient(
            base_url="http://127.0.0.1:1234/v1",
            model_name="local-model",
            client_factory=lambda **_: FakeClient(FakeCompletions(error=RuntimeError("connection refused"))),
        )

        with self.assertRaisesRegex(LlmClientError, "LLM request failed: connection refused"):
            client.prompt("ping")

    def test_llm_client_surfaces_missing_content_error(self) -> None:
        client = LlmClient(
            base_url="http://127.0.0.1:1234/v1",
            model_name="local-model",
            client_factory=lambda **_: FakeClient(FakeCompletions(response=FakeResponse(None))),
        )

        with self.assertRaisesRegex(
            LlmClientError,
            "LLM response did not contain message content",
        ):
            client.prompt("ping")

    def test_ui_defaults_include_required_input_fields(self) -> None:
        defaults = default_form_values()

        self.assertIsInstance(defaults, UiDefaults)
        self.assertEqual(defaults.input_dir, "")
        self.assertEqual(defaults.output_dir, "./output")
        self.assertEqual(defaults.lmstudio_base_url, "http://127.0.0.1:1234/v1")
        self.assertEqual(defaults.model_name, "")

    def test_ui_run_handler_accepts_valid_inputs(self) -> None:
        runner = FakeRunner(
            DockerRunResult(
                command=["docker", "run"],
                returncode=0,
                stdout="ok",
                stderr="",
            )
        )

        response = handle_run_request(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            },
            runner=runner,
        )

        self.assertIsInstance(response, UiRunResponse)
        self.assertIsInstance(response.config, AppConfig)
        self.assertEqual(response.status_message, "Container run completed successfully.")
        self.assertEqual(response.result, runner.result)
        self.assertIsNotNone(runner.received_config)

    def test_ui_run_handler_returns_clear_error_for_invalid_inputs(self) -> None:
        response = handle_run_request(
            {
                "input_dir": "",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            }
        )

        self.assertIsNone(response.config)
        self.assertEqual(response.status_message, "Missing required configuration value: input_dir")
        self.assertIsNone(response.result)

    def test_ui_run_handler_returns_runner_failure_message(self) -> None:
        runner = FakeRunner(
            DockerRunResult(
                command=["docker", "run"],
                returncode=1,
                stdout="",
                stderr="boom",
            )
        )

        response = handle_run_request(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            },
            runner=runner,
        )

        self.assertEqual(response.status_message, "Container run failed: boom")
        self.assertEqual(response.result, runner.result)

    def test_main_entrypoint_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "app.main"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Female Character Network Visualizer scaffold", result.stdout)
        self.assertIn("streamlit run app/ui/app.py", result.stdout)
        self.assertIn("UI launches Docker container", result.stdout)

    def test_requirements_include_core_dependencies(self) -> None:
        requirements = Path("requirements.txt").read_text(encoding="utf-8")

        for dependency in ["networkx", "pyvis", "pandas", "streamlit", "openai"]:
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, requirements)


if __name__ == "__main__":
    unittest.main()
