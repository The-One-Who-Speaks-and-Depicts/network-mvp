"""Runtime service and integration tests."""

# Focused suites intentionally share realistic setup snippets.
# pylint: disable=duplicate-code

import io
from pathlib import Path
import subprocess
import tempfile
from unittest import mock

from app import main as app_main
from app.services import llm_client as llm_client_module
from app.config import AppConfig
from app.services.docker_runner import DockerRunResult, DockerRunner
from app.services.llm_client import LlmClient, LlmClientError, LlmResponse
from app.ui.shell import UiDefaults, UiRunResponse, default_form_values, handle_run_request
from tests.test_support import (
    FakeClient,
    FakeCompletions,
    FakeLlmClient,
    FakeResponse,
    FakeRunner,
    ScaffoldTestBase,
)


class RuntimeTests(ScaffoldTestBase):
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
        self.assertIn("--network", command)
        self.assertIn("host", command)
        self.assertNotIn("--add-host", command)
        self.assertIn("NETWORK_MVP_INPUT_DIR=/data/input", command)
        self.assertIn("NETWORK_MVP_OUTPUT_DIR=/data/output", command)
        self.assertIn(
            "NETWORK_MVP_LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1",
            command,
        )
        self.assertIn("NETWORK_MVP_MODEL_NAME=local-model", command)
        self.assertIn("NETWORK_MVP_ENABLE_SEMANTIC_ANNOTATION=true", command)
        self.assertIn("NETWORK_MVP_ENABLE_DEBUG_LOGGING=false", command)
        self.assertIn("network-mvp:test", command)

    def test_docker_runner_uses_host_network_for_host_docker_internal(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://host.docker.internal:1234/v1",
                "model_name": "local-model",
            }
        )

        command = DockerRunner(image_name="network-mvp:test").build_command(config)

        self.assertIn("--network", command)
        self.assertIn("host", command)
        self.assertNotIn("--add-host", command)
        self.assertIn(
            "NETWORK_MVP_LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1",
            command,
        )

    def test_docker_runner_leaves_non_local_lmstudio_url_unchanged(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "./data",
                "output_dir": "./output",
                "lmstudio_base_url": "http://lmstudio.internal:1234/v1",
                "model_name": "local-model",
            }
        )

        command = DockerRunner(image_name="network-mvp:test").build_command(config)

        self.assertNotIn("--add-host", command)
        self.assertIn(
            "NETWORK_MVP_LMSTUDIO_BASE_URL=http://lmstudio.internal:1234/v1",
            command,
        )

    def test_docker_runner_builds_image_before_run(self) -> None:
        runner = DockerRunner(image_name="network-mvp:test")

        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            (Path(input_temp_dir) / "corpus.txt").write_text("text", encoding="utf-8")
            config = AppConfig.from_mapping(
                {
                    "input_dir": input_temp_dir,
                    "output_dir": output_temp_dir,
                    "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                    "model_name": "local-model",
                }
            )
            with mock.patch("app.services.docker_runner.subprocess.run") as mock_run:
                mock_run.side_effect = [
                    subprocess.CompletedProcess(
                        ["docker", "build", "-t", "network-mvp:test", "."],
                        0,
                        stdout="built",
                        stderr="",
                    ),
                    subprocess.CompletedProcess(
                        ["docker", "run"],
                        0,
                        stdout="ok",
                        stderr="",
                    ),
                ]

                result = runner.run(config)

        self.assertTrue(result.succeeded)
        self.assertEqual(mock_run.call_args_list[0].kwargs["cwd"], runner.project_root)
        self.assertEqual(
            mock_run.call_args_list[0].args[0],
            ["docker", "build", "-t", "network-mvp:test", "."],
        )

    def test_docker_runner_returns_build_failure_when_image_build_fails(self) -> None:
        runner = DockerRunner(image_name="network-mvp:test")

        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            (Path(input_temp_dir) / "corpus.txt").write_text("text", encoding="utf-8")
            config = AppConfig.from_mapping(
                {
                    "input_dir": input_temp_dir,
                    "output_dir": output_temp_dir,
                    "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                    "model_name": "local-model",
                }
            )
            with mock.patch("app.services.docker_runner.subprocess.run") as mock_run:
                mock_run.side_effect = [
                    subprocess.CompletedProcess(
                        ["docker", "build", "-t", "network-mvp:test", "."],
                        1,
                        stdout="",
                        stderr="build failed",
                    ),
                ]

                result = runner.run(config)

        self.assertFalse(result.succeeded)
        self.assertEqual(result.command, ["docker", "build", "-t", "network-mvp:test", "."])
        self.assertEqual(result.stderr, "build failed")

    def test_docker_runner_rejects_invalid_input_before_building(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "/path/that/does/not/exist",
                "output_dir": "./output",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
            }
        )
        runner = DockerRunner(image_name="network-mvp:test")

        with mock.patch("app.services.docker_runner.subprocess.run") as mock_run:
            result = runner.run(config)

        self.assertFalse(result.succeeded)
        self.assertEqual(result.command, [])
        self.assertIn("does not exist", result.stderr)
        mock_run.assert_not_called()

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

    def test_llm_client_default_factory_supplies_lm_studio_api_key(self) -> None:
        fake_openai_class = mock.Mock(return_value=object())
        fake_openai_module = type("FakeOpenAiModule", (), {"OpenAI": fake_openai_class})()

        with (
            mock.patch(
                "app.services.llm_client.importlib.import_module",
                return_value=fake_openai_module,
            ),
            mock.patch.dict(llm_client_module.os.environ, {}, clear=True),
        ):
            client = LlmClient(
                base_url="http://127.0.0.1:1234/v1",
                model_name="local-model",
            )

        self.assertIsInstance(client, LlmClient)
        fake_openai_class.assert_called_once_with(
            base_url="http://127.0.0.1:1234/v1",
            timeout=60.0,
            api_key="lm-studio",
        )

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
            client_factory=lambda **_: FakeClient(
                FakeCompletions(error=RuntimeError("connection refused"))
            ),
        )

        with self.assertRaisesRegex(
            LlmClientError,
            (
                "LLM request failed\\. base_url=http://127.0.0.1:1234/v1 "
                "model=local-model details=RuntimeError"
            ),
        ):
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
        self.assertEqual(defaults.lmstudio_base_url, "http://host.docker.internal:1234/v1")
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
        self.assertIsNotNone(response.progress_state)
        progress_state = response.progress_state
        if progress_state is None:
            self.fail("expected progress state")
        self.assertEqual(progress_state.current_stage, "completed")

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
        self.assertIsNotNone(response.progress_state)
        progress_state = response.progress_state
        if progress_state is None:
            self.fail("expected progress state")
        self.assertEqual(progress_state.status, "failed")

    def test_main_entrypoint_runs_pipeline_and_reports_progress(self) -> None:
        fake_client = FakeLlmClient(
            responses=[
                "княгиня грикша пишет к ѥсифу",
                "княгиня грикша писать к ѥсифъ",
                "Княгиня Грикша\tкнягиня грикша\nѤсифъ\tѥсифу",
                "female",
                "not_inferred",
                "not stated\t\t0.2",
            ]
        )

        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            input_dir = Path(input_temp_dir)
            output_dir = Path(output_temp_dir)
            (input_dir / "003.003.txt").write_text(
                "Княгиня Грикша пишет к ѥсифу.",
                encoding="utf-8",
            )

            buffer = io.StringIO()
            with (
                mock.patch(
                    "app.main.LlmClient.from_config",
                    return_value=fake_client,
                ),
                mock.patch.dict(
                    "os.environ",
                    {
                        "NETWORK_MVP_INPUT_DIR": str(input_dir),
                        "NETWORK_MVP_OUTPUT_DIR": str(output_dir),
                        "NETWORK_MVP_LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
                        "NETWORK_MVP_MODEL_NAME": "local-model",
                    },
                    clear=False,
                ),
                mock.patch("sys.stdout", buffer),
            ):
                app_main.main()

            stdout = buffer.getvalue()
            self.assertIn("PROGRESS\tstage=startup", stdout)
            self.assertIn("PROGRESS\tstage=ingestion\tcompleted=1\ttotal=1", stdout)
            self.assertIn("PROGRESS\tstage=graph_export\tcompleted=1\ttotal=1", stdout)
            self.assertTrue((output_dir / "graph.json").is_file())
            self.assertTrue((output_dir / "graph.html").is_file())

    def test_main_entrypoint_rejects_invalid_environment(self) -> None:
        with (
            mock.patch.dict(
                "os.environ",
                {
                    "NETWORK_MVP_INPUT_DIR": "input",
                    "NETWORK_MVP_OUTPUT_DIR": "output",
                    "NETWORK_MVP_LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
                    "NETWORK_MVP_MODEL_NAME": "local-model",
                    "NETWORK_MVP_ENABLE_DEBUG_LOGGING": "maybe",
                },
                clear=True,
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            with self.assertRaisesRegex(
                SystemExit,
                "Invalid boolean configuration value for enable_debug_logging",
            ):
                app_main.main()

        self.assertIn("Configuration error:", stderr.getvalue())

    def test_main_entrypoint_fails_fast_on_first_normalization_llm_error(self) -> None:
        fake_client = FakeLlmClient(error=LlmClientError("connection refused"))

        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            input_dir = Path(input_temp_dir)
            output_dir = Path(output_temp_dir)
            (input_dir / "003.003.txt").write_text(
                "Княгиня Грикша пишет к ѥсифу.",
                encoding="utf-8",
            )

            buffer = io.StringIO()
            with (
                mock.patch(
                    "app.main.LlmClient.from_config",
                    return_value=fake_client,
                ),
                mock.patch.dict(
                    "os.environ",
                    {
                        "NETWORK_MVP_INPUT_DIR": str(input_dir),
                        "NETWORK_MVP_OUTPUT_DIR": str(output_dir),
                        "NETWORK_MVP_LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
                        "NETWORK_MVP_MODEL_NAME": "local-model",
                    },
                    clear=False,
                ),
                mock.patch("sys.stdout", buffer),
            ):
                with self.assertRaises(SystemExit) as error_context:
                    app_main.main()

            stdout = buffer.getvalue()
            self.assertIn("PROGRESS\tstage=ingestion\tcompleted=1\ttotal=1", stdout)
            self.assertIn(
                "PROGRESS\tstage=normalization\tcompleted=0\ttotal=1\tstatus=failed",
                stdout,
            )
            self.assertNotIn("PROGRESS\tstage=lemmatization", stdout)
            self.assertIn("Normalization failed on first file", str(error_context.exception))
            self.assertTrue(
                (output_dir / "logs" / "normalization" / "text_0001_003.003.txt.log").is_file()
            )
