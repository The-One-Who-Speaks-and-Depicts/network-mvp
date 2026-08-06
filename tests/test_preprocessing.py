"""Preprocessing pipeline tests."""

# Focused suites intentionally share realistic setup snippets.
from tests.test_support import (
    AppConfig,
    ConfigError,
    FakeLlmClient,
    FileIngestionService,
    InputDirectoryError,
    LemmatizationService,
    LemmatizedFile,
    LlmClientError,
    NormalizationService,
    NormalizationStageError,
    NormalizedFile,
    Path,
    SourceFile,
    tempfile,
    mock,
    ScaffoldTestBase,
)


# Preprocessing tests keep temporary-corpus setup beside the stage under test;
# this makes file/encoding and artifact behavior directly readable.
# pylint: disable=duplicate-code
class PreprocessingTests(ScaffoldTestBase):
    def test_required_directories_exist(self) -> None:
        for path in [
            Path("app"),
            Path("app/ui"),
            Path("app/pipeline"),
            Path("app/graph"),
            Path("app/progress"),
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
            Path("app/graph/build.py"),
            Path("app/graph/export.py"),
            Path("app/progress/reporting.py"),
            Path("app/pipeline/file_ingestion.py"),
            Path("app/pipeline/normalization.py"),
            Path("app/pipeline/lemmatization.py"),
            Path("app/pipeline/entities.py"),
            Path("app/pipeline/entity_merge.py"),
            Path("app/pipeline/cooccurrence.py"),
            Path("app/pipeline/semantic_relations.py"),
            Path("app/services/docker_runner.py"),
            Path("app/services/llm_client.py"),
            Path("prompts/normalization_prompt.txt"),
            Path("prompts/lemmatization_prompt.txt"),
            Path("prompts/entity_extraction_prompt.txt"),
            Path("prompts/entity_gender_prompt.txt"),
            Path("prompts/semantic_relation_prompt.txt"),
            Path("requirements.txt"),
            Path("pyproject.toml"),
            Path("RUNBOOK.md"),
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

    def test_config_from_mapping_uses_default_flags(self) -> None:
        config = AppConfig.from_mapping(
            {
                "input_dir": "input-data",
                "output_dir": "output-data",
                "lmstudio_base_url": "http://localhost:1234/v1",
                "model_name": "local-model",
            }
        )

        self.assertTrue(config.enable_semantic_annotation)
        self.assertFalse(config.enable_debug_logging)

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

    def test_file_ingestion_preserves_nested_paths_without_nested_log_paths(self) -> None:
        service = FileIngestionService()
        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
            input_dir = Path(input_temp_dir)
            (input_dir / "a").mkdir()
            (input_dir / "b").mkdir()
            (input_dir / "a" / "same.txt").write_text("A", encoding="utf-8")
            (input_dir / "b" / "same.txt").write_text("B", encoding="utf-8")

            source_files = service.load_source_files(input_dir)
            service.export_original_logs(source_files, Path(output_temp_dir))

            self.assertEqual(
                [source_file.filename for source_file in source_files],
                ["a/same.txt", "b/same.txt"],
            )
            self.assertEqual(
                sorted(
                    path.name
                    for path in (Path(output_temp_dir) / "logs" / "original").iterdir()
                ),
                ["text_0001_same.txt", "text_0002_same.txt"],
            )

    def test_file_ingestion_rejects_missing_or_empty_input_directory(self) -> None:
        service = FileIngestionService()

        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir) / "empty"
            empty_dir.mkdir()
            with self.assertRaisesRegex(InputDirectoryError, r"contains no \.txt files"):
                service.load_source_files(empty_dir)

        with self.assertRaisesRegex(InputDirectoryError, "does not exist"):
            service.load_source_files(Path("/path/that/does/not/exist"))

    def test_file_ingestion_reports_invalid_utf8_without_double_decoding(self) -> None:
        service = FileIngestionService()
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir)
            invalid_file = input_dir / "invalid.txt"
            invalid_file.write_bytes(b"\xff")

            with self.assertRaisesRegex(InputDirectoryError, "not valid UTF-8"):
                service.load_source_files(input_dir)

    def test_file_ingestion_reports_access_failures(self) -> None:
        service = FileIngestionService()
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir)
            (input_dir / "blocked.txt").write_text("text", encoding="utf-8")
            with mock.patch.object(
                Path,
                "read_text",
                side_effect=PermissionError("permission denied"),
            ):
                with self.assertRaisesRegex(InputDirectoryError, "Could not access corpus file"):
                    service.load_source_files(input_dir)

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
        with (
            tempfile.TemporaryDirectory() as input_temp_dir,
            tempfile.TemporaryDirectory() as output_temp_dir,
        ):
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
            self.assertTrue(
                (output_dir / "logs" / "original" / "text_0001_letter.txt").is_file()
            )

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
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("error_category: invalid_model_output", log_text)
            self.assertIn("empty normalization output", log_text)

    def test_normalization_nested_failure_log_uses_flat_safe_name(self) -> None:
        service = NormalizationService(FakeLlmClient(responses=[" "]))
        source_files = [
            SourceFile(
                file_id="text_0001",
                filename="a/letter.txt",
                source_path=Path("/tmp/a/letter.txt"),
                text="raw text",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            service.normalize_files(source_files, output_dir)

            log_path = output_dir / "logs" / "normalization" / "text_0001_letter.txt.log"
            self.assertTrue(log_path.is_file())

    def test_normalization_raises_for_first_llm_error_and_writes_detailed_log(self) -> None:
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
            log_path = output_dir / "logs" / "normalization" / "text_0001_letter.txt.log"

            with self.assertRaises(NormalizationStageError) as error_context:
                service.normalize_files(source_files, output_dir)

            self.assertTrue(log_path.is_file())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("error_type: LlmClientError", log_text)
            self.assertIn("error_category: llm_request", log_text)
            self.assertIn("error_message: request failed", log_text)
            self.assertIn("traceback:", log_text)
            self.assertIn("LlmClientError: request failed", log_text)
            self.assertIn("source_text:\nraw text", log_text)
            self.assertIn("prompt:", log_text)
            self.assertIn("See log:", str(error_context.exception))

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

            self.assertEqual(
                [file.file_id for file in normalized_files],
                ["text_0001", "text_0002", "text_0003"],
            )
            self.assertEqual(
                [file.filename for file in normalized_files],
                ["003.003.txt", "004.004.txt", "005.005.txt"],
            )
            self.assertEqual(
                [file.normalized_text for file in normalized_files],
                [
                    "поклонъ ѿ грикши къ ѥсифу приславъ ꙩнаньꙗ молви♮ ꙗзъ ѥму ѿвѣчалъ",
                    "ѿ микит·ѣ · ко цертѹ · цто ѥсм·ь · ♮руцилъ · ѹ петра",
                    "♮но ѿ давꙑ♮ ♮есиѳа · къ матѳѣю · постои · за нашего сироту ·",
                ],
            )
            self.assertTrue(
                (output_dir / "normalized" / "text_0001_003.003.txt").is_file()
            )
            self.assertTrue(
                (output_dir / "normalized" / "text_0002_004.004.txt").is_file()
            )
            self.assertTrue(
                (output_dir / "normalized" / "text_0003_005.005.txt").is_file()
            )
            self.assertIn("поклонъ ѿ грикши", client.prompts[0])
    def test_lemmatization_writes_output(self) -> None:
        client = FakeLlmClient(responses=["поклонъ грикша къ ѥсифъ"])
        service = LemmatizationService(client)
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="letter.txt",
                normalized_text="поклонъ грикши къ ѥсифу",
                output_path=Path("/tmp/text_0001_letter.txt"),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lemmatized_files = service.lemmatize_files(normalized_files, output_dir)
            output_path = output_dir / "lemmas" / "text_0001_letter.txt"

            self.assertEqual(len(lemmatized_files), 1)
            self.assertIsInstance(lemmatized_files[0], LemmatizedFile)
            self.assertEqual(lemmatized_files[0].lemma_text, "поклонъ грикша къ ѥсифъ")
            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "поклонъ грикша къ ѥсифъ")

    def test_lemmatization_writes_log_for_empty_output(self) -> None:
        client = FakeLlmClient(responses=["   "])
        service = LemmatizationService(client)
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="letter.txt",
                normalized_text="поклонъ грикши къ ѥсифу",
                output_path=Path("/tmp/text_0001_letter.txt"),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lemmatized_files = service.lemmatize_files(normalized_files, output_dir)
            log_path = output_dir / "logs" / "lemmatization" / "text_0001_letter.txt.log"

            self.assertEqual(lemmatized_files, [])
            self.assertTrue(log_path.is_file())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("error_category: invalid_model_output", log_text)
            self.assertIn("empty lemmatization output", log_text)

    def test_lemmatization_nested_failure_log_uses_flat_safe_name(self) -> None:
        service = LemmatizationService(FakeLlmClient(responses=[" "]))
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="a/letter.txt",
                normalized_text="raw text",
                output_path=Path("/tmp/text_0001_letter.txt"),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            service.lemmatize_files(normalized_files, output_dir)

            log_path = output_dir / "logs" / "lemmatization" / "text_0001_letter.txt.log"
            self.assertTrue(log_path.is_file())

    def test_lemmatization_writes_log_for_llm_error(self) -> None:
        client = FakeLlmClient(error=LlmClientError("request failed"))
        service = LemmatizationService(client)
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="letter.txt",
                normalized_text="поклонъ грикши къ ѥсифу",
                output_path=Path("/tmp/text_0001_letter.txt"),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lemmatized_files = service.lemmatize_files(normalized_files, output_dir)
            log_path = output_dir / "logs" / "lemmatization" / "text_0001_letter.txt.log"

            self.assertEqual(lemmatized_files, [])
            self.assertTrue(log_path.is_file())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("error_category: llm_request", log_text)
            self.assertIn("request failed", log_text)

    def test_lemmatization_with_zenodo_birchbark_fixtures(self) -> None:
        normalized_files = [
            NormalizedFile(
                file_id="text_0001",
                filename="003.003.txt",
                normalized_text="поклонъ ѿ грикши къ ѥсифу приславъ ꙩнаньꙗ молви♮ ꙗзъ ѥму ѿвѣчалъ",
                output_path=Path("/tmp/text_0001_003.003.txt"),
            ),
            NormalizedFile(
                file_id="text_0002",
                filename="004.004.txt",
                normalized_text="ѿ микит·ѣ · ко цертѹ · цто ѥсм·ь · ♮руцилъ · ѹ петра",
                output_path=Path("/tmp/text_0002_004.004.txt"),
            ),
            NormalizedFile(
                file_id="text_0003",
                filename="005.005.txt",
                normalized_text="♮но ѿ давꙑ♮ ♮есиѳа · къ матѳѣю · постои · за нашего сироту ·",
                output_path=Path("/tmp/text_0003_005.005.txt"),
            ),
        ]
        client = FakeLlmClient(
            responses=[
                "поклонъ ѿ грикша къ ѥсифъ\n прислати ꙩнаньꙗ молвити ꙗзъ ѥмоу ѿвѣчати",
                "ѿ микита · ко цертъ ·\n что ѥсмь · ручити · ѹ петръ",
                "но ѿ давы ♮есиѳа ·\n къ матѳѣи · постоѧти · за нашь сирота ·",
            ]
        )
        service = LemmatizationService(client)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            lemmatized_files = service.lemmatize_files(normalized_files, output_dir)

            self.assertEqual(
                [file.file_id for file in lemmatized_files],
                ["text_0001", "text_0002", "text_0003"],
            )
            self.assertEqual(
                [file.filename for file in lemmatized_files],
                ["003.003.txt", "004.004.txt", "005.005.txt"],
            )
            self.assertEqual(
                [file.lemma_text for file in lemmatized_files],
                [
                    "поклонъ ѿ грикша къ ѥсифъ прислати ꙩнаньꙗ молвити ꙗзъ ѥмоу ѿвѣчати",
                    "ѿ микита · ко цертъ · что ѥсмь · ручити · ѹ петръ",
                    "но ѿ давы ♮есиѳа · къ матѳѣи · постоѧти · за нашь сирота ·",
                ],
            )
            self.assertTrue(
                (output_dir / "lemmas" / "text_0001_003.003.txt").is_file()
            )
            self.assertTrue(
                (output_dir / "lemmas" / "text_0002_004.004.txt").is_file()
            )
            self.assertTrue(
                (output_dir / "lemmas" / "text_0003_005.005.txt").is_file()
            )
            self.assertIn("поклонъ ѿ грикши", client.prompts[0])
