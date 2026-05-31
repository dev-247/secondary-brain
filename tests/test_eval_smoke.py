from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.eval_smoke import SmokeCase, load_cases, run_smoke_eval


def fake_embedding(text: str) -> list[float]:
    buckets = [0.0, 0.0, 0.0, 0.0]
    for index, char in enumerate(text.lower()):
        buckets[index % len(buckets)] += float(ord(char) % 17)
    magnitude = sum(value * value for value in buckets) ** 0.5 or 1.0
    return [value / magnitude for value in buckets]


class SmokeEvalTests(unittest.TestCase):
    def test_load_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(
                json.dumps([{"query": "What is alpha?", "expected_path": "alpha.md"}]),
                encoding="utf-8",
            )

            self.assertEqual(load_cases(path), [SmokeCase("What is alpha?", "alpha.md", 3)])

    def test_load_cases_accepts_expected_rank(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "query": "What is alpha?",
                            "expected_path": "alpha.md",
                            "expected_rank_at_most": 1,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(load_cases(path), [SmokeCase("What is alpha?", "alpha.md", 1)])

    def test_smoke_eval_finds_expected_sources(self) -> None:
        fixture_root = Path(__file__).parent / "fixtures" / "smoke_vault"
        cases = [
            SmokeCase("What is Project Alpha's main goal?", "project-alpha.md", 3),
            SmokeCase("What exercise habit is preferred in the health notes?", "health-notes.md", 3),
        ]

        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.embeddings.embed_text", side_effect=fake_embedding):
                with patch("scripts.ingest.embed_text", side_effect=fake_embedding):
                    with patch("scripts.search.embed_text", side_effect=fake_embedding):
                        result = run_smoke_eval(
                            vault_root=fixture_root,
                            cases=cases,
                            qdrant_path=Path(directory) / "qdrant",
                            collection_name="test_second_brain",
                        )

        self.assertTrue(result.ok)
        self.assertEqual(result.passed, 2)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.recall, 1.0)


if __name__ == "__main__":
    unittest.main()
