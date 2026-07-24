from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.config import AppConfig, ConfigError
from app.pipeline.file_ingestion import FileIngestionService, SourceFile
from app.pipeline.normalization import NormalizationService, NormalizedFile
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


class FakeLlmClient:
    def __init__(self, responses: list[str] | None = None, error: Exception | None = None) -> None:
        self.responses = responses or []
        self.error = error
        self.prompts: list[str] = []

    def prompt(self, prompt_text: str, system_prompt: str | None = None) -> LlmResponse:
        self.prompts.append(prompt_text)
        if self.error is not None:
            raise self.error
        if not self.responses:
            return LlmResponse(text="", raw_response=None)
        return LlmResponse(text=self.responses.pop(0), raw_response=None)


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
            Path("app/pipeline/file_ingestion.py"),
            Path("app/pipeline/normalization.py"),
            Path("app/services/docker_runner.py"),
            Path("app/services/llm_client.py"),
            Path("prompts/normalization_prompt.txt"),
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

    def test_file_ingestion_discovers_only_txt_files(self) -> None:
        service = FileIngestionService()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.txt").write_text("A", encoding="utf-8")
            (root / "b.md").write_text("B", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "c.txt").write_text("C", encoding="utf-8")

            paths = service.discover_text_files(root)

        self.assertEqual([path.name for path in paths], ["a.txt", "c.txt"])

    def test_file_ingestion_loads_source_files_with_stable_ids(self) -> None:
        service = FileIngestionService()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "b.txt").write_text("Beta", encoding="utf-8")
            (root / "a.txt").write_text("Alpha", encoding="utf-8")

            source_files = service.load_source_files(root)

        self.assertEqual([file.file_id for file in source_files], ["text_0001", "text_0002"])
        self.assertEqual([file.filename for file in source_files], ["a.txt", "b.txt"])
        self.assertEqual([file.text for file in source_files], ["Alpha", "Beta"])
        self.assertTrue(all(isinstance(file, SourceFile) for file in source_files))

    def test_file_ingestion_exports_original_logs(self) -> None:
        service = FileIngestionService()
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="letter.txt",
                source_path=Path("/tmp/letter.txt"),
                text="Original text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            log_dir = service.export_original_logs(source_files, output_dir)
            log_path = log_dir / "text_0001_letter.txt"

            self.assertEqual(log_dir, output_dir / "logs" / "original")
            self.assertTrue(log_path.is_file())
            self.assertEqual(log_path.read_text(encoding="utf-8"), "Original text")

    def test_file_ingestion_ingest_writes_logs_outside_container_mount(self) -> None:
        service = FileIngestionService()
        with tempfile.TemporaryDirectory() as input_temp_dir, tempfile.TemporaryDirectory() as output_temp_dir:
            input_dir = Path(input_temp_dir)
            output_dir = Path(output_temp_dir)
            (input_dir / "letter.txt").write_text("Text body", encoding="utf-8")
            config = AppConfig.from_mapping(
                {
                    "input_dir": input_dir,
                    "output_dir": output_dir,
                    "lmstudio_base_url": "http://127.0.0.1:1234/v1",
                    "model_name": "local-model",
                }
            )

            source_files = service.ingest(config)

            self.assertEqual(len(source_files), 1)
            self.assertTrue((output_dir / "logs" / "original" / "text_0001_letter.txt").is_file())

    def test_normalization_removes_line_breaks_and_writes_output(self) -> None:
        client = FakeLlmClient(responses=["first line\nsecond line"])
        service = NormalizationService(client)
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="letter.txt",
                source_path=Path("/tmp/letter.txt"),
                text="raw text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            normalized_files = service.normalize_files(source_files, output_dir)
            output_path = output_dir / "normalized" / "text_0001_letter.txt"

            self.assertEqual(len(normalized_files), 1)
            self.assertIsInstance(normalized_files[0], NormalizedFile)
            self.assertEqual(normalized_files[0].normalized_text, "first line second line")
            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "first line second line")

    def test_normalization_writes_log_for_empty_output(self) -> None:
        client = FakeLlmClient(responses=["   "])
        service = NormalizationService(client)
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="letter.txt",
                source_path=Path("/tmp/letter.txt"),
                text="raw text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            normalized_files = service.normalize_files(source_files, output_dir)
            log_path = output_dir / "logs" / "normalization" / "text_0001_letter.txt.log"

            self.assertEqual(normalized_files, [])
            self.assertTrue(log_path.is_file())
            self.assertIn("empty normalization output", log_path.read_text(encoding="utf-8"))

    def test_normalization_writes_log_for_llm_error(self) -> None:
        client = FakeLlmClient(error=LlmClientError("request failed"))
        service = NormalizationService(client)
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="letter.txt",
                source_path=Path("/tmp/letter.txt"),
                text="raw text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            normalized_files = service.normalize_files(source_files, output_dir)
            log_path = output_dir / "logs" / "normalization" / "text_0001_letter.txt.log"

            self.assertEqual(normalized_files, [])
            self.assertTrue(log_path.is_file())
            self.assertIn("request failed", log_path.read_text(encoding="utf-8"))

    def test_normalization_with_zenodo_birchbark_fixtures(self) -> None:
        fixture_dir = Path("tests/fixtures/zenodo_birchbark")
        source_files = FileIngestionService().load_source_files(fixture_dir)
        client = FakeLlmClient(
            responses=[
                "поклонъ ѿ грикши къ ѥсифу\n приславъ ꙩнаньꙗ молви♮ ꙗзъ ѥму ѿвѣчалъ",
                "ѿ микит·ѣ · ко цертѹ ·\n цто ѥсм·ь · ♮руцилъ · ѹ петра",
                "♮но ѿ давꙑ♮ ♮есиѳа ·\n къ матѳѣю · постои · за нашего сироту ·",
            ]
        )
        service = NormalizationService(client)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            normalized_files = service.normalize_files(source_files, output_dir)

            self.assertEqual([file.file_id for file in normalized_files], ["text_0001", "text_0002", "text_0003"])
            self.assertEqual([file.filename for file in normalized_files], ["003.003.txt", "004.004.txt", "005.005.txt"])
            self.assertEqual(
                [file.normalized_text for file in normalized_files],
                [
                    "поклонъ ѿ грикши къ ѥсифу приславъ ꙩнаньꙗ молви♮ ꙗзъ ѥму ѿвѣчалъ",
                    "ѿ микит·ѣ · ко цертѹ · цто ѥсм·ь · ♮руцилъ · ѹ петра",
                    "♮но ѿ давꙑ♮ ♮есиѳа · къ матѳѣю · постои · за нашего сироту ·",
                ],
            )
            self.assertTrue((output_dir / "normalized" / "text_0001_003.003.txt").is_file())
            self.assertTrue((output_dir / "normalized" / "text_0002_004.004.txt").is_file())
            self.assertTrue((output_dir / "normalized" / "text_0003_005.005.txt").is_file())
            self.assertIn("поклонъ ѿ грикши", client.prompts[0])

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
