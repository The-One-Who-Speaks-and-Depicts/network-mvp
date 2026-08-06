"""Documentation and operator guidance tests."""

from pathlib import Path

from tests.test_support import ScaffoldTestBase


class DocumentationTests(ScaffoldTestBase):
    def test_runbook_documents_lm_studio_and_manual_cleanup(self) -> None:
        runbook = Path("RUNBOOK.md").read_text(encoding="utf-8")

        self.assertIn("LM Studio", runbook)
        self.assertIn("not stated", runbook)
        self.assertIn("graph.json", runbook)
        self.assertIn("graph.html", runbook)
        self.assertIn("lemmatized text", runbook)

    def test_requirements_include_core_dependencies(self) -> None:
        requirements = Path("requirements.txt").read_text(encoding="utf-8")

        for dependency in ["networkx", "pyvis", "pandas", "streamlit", "openai", "pylint", "mypy"]:
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, requirements)
