from pathlib import Path
import subprocess
import sys
import unittest

from app.config import AppConfig


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
            Path("output/.gitkeep"),
            Path("logs/.gitkeep"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_config_defaults_are_constructible(self) -> None:
        config = AppConfig()
        self.assertEqual(config.lmstudio_base_url, "")
        self.assertEqual(config.model_name, "")
        self.assertIsNone(config.input_dir)
        self.assertIsNone(config.output_dir)

    def test_main_entrypoint_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "app.main"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Female Character Network Visualizer scaffold", result.stdout)


if __name__ == "__main__":
    unittest.main()
