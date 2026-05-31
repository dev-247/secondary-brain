from __future__ import annotations

import unittest

from scripts.doctor import missing_models, parse_ollama_models


class DoctorTests(unittest.TestCase):
    def test_parse_ollama_models_skips_header_and_tags(self) -> None:
        output = """NAME                       ID              SIZE      MODIFIED
llama3.2:latest            a80c4f17acd5    2.0 GB    5 hours ago
nomic-embed-text:latest    0a109f422b47    274 MB    5 hours ago
"""

        self.assertEqual(
            parse_ollama_models(output),
            {"llama3.2", "llama3.2:latest", "nomic-embed-text", "nomic-embed-text:latest"},
        )

    def test_missing_models_accepts_base_model_names(self) -> None:
        installed = {"llama3.2:latest", "llama3.2", "nomic-embed-text"}

        self.assertEqual(missing_models(installed), [])

    def test_missing_models_reports_absent_models(self) -> None:
        installed = {"llama3.2"}

        self.assertEqual(missing_models(installed), ["nomic-embed-text"])


if __name__ == "__main__":
    unittest.main()
