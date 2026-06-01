from __future__ import annotations

import unittest

from unittest.mock import patch

from scripts.router import (
    ABSTENTION_MESSAGE,
    assess_source_coverage,
    choose_mode,
    normalize_answer,
    validate_answer_citations,
    synthesize_answer,
    synthesize_answer_result,
)
from scripts.search import SearchResult


def source(content: str, score: float = 0.7, lexical_score: float = 0.5) -> SearchResult:
    return SearchResult(
        content=content,
        filename="note.md",
        path="note.md",
        heading="Note",
        chunk_index=0,
        score=score,
        lexical_score=lexical_score,
    )


class RouterTests(unittest.TestCase):
    def test_short_query_uses_fast_mode(self) -> None:
        self.assertEqual(choose_mode("What is this note about?"), "fast")

    def test_analytical_query_uses_deep_mode(self) -> None:
        query = "Compare these notes and explain in detail what contradictions exist."

        self.assertEqual(choose_mode(query), "deep")

    def test_force_deep_overrides_query_shape(self) -> None:
        self.assertEqual(choose_mode("Short?", force_deep=True), "deep")

    def test_source_coverage_accepts_supported_query(self) -> None:
        coverage = assess_source_coverage(
            "What is the project alpha goal?",
            [source("Project Alpha goal is grounded answers with citations.")],
        )

        self.assertTrue(coverage.supported)
        self.assertEqual(coverage.confidence, "high")

    def test_source_coverage_rejects_weak_sources(self) -> None:
        coverage = assess_source_coverage(
            "What is the project alpha goal?",
            [source("Morning hydration and evening walks.", score=0.1, lexical_score=0.0)],
        )

        self.assertFalse(coverage.supported)
        self.assertEqual(coverage.confidence, "low")

    def test_synthesize_refuses_when_source_coverage_is_weak(self) -> None:
        answer, mode = synthesize_answer(
            "What is the project alpha goal?",
            [source("Morning hydration and evening walks.", score=0.1, lexical_score=0.0)],
            mode="fast",
        )

        self.assertEqual(answer, ABSTENTION_MESSAGE)
        self.assertEqual(mode, "none")

    def test_normalize_answer_standardizes_model_abstention(self) -> None:
        self.assertEqual(normalize_answer("I don't know."), ABSTENTION_MESSAGE)
        self.assertEqual(normalize_answer("No information found in your knowledge base."), ABSTENTION_MESSAGE)

    def test_validate_answer_citations_requires_bracketed_sources(self) -> None:
        self.assertTrue(validate_answer_citations("Project Alpha keeps documents local [1]."))
        self.assertFalse(validate_answer_citations("Project Alpha keeps documents local."))
        self.assertTrue(validate_answer_citations(ABSTENTION_MESSAGE))

    def test_synthesize_answer_result_includes_confidence(self) -> None:
        with patch("scripts.router._chat_ollama", return_value="Grounded answer [1]."):
            result = synthesize_answer_result(
                "What is the project alpha goal?",
                [source("Project Alpha goal is grounded answers with citations.")],
                mode="fast",
            )

        self.assertEqual(result.answer, "Grounded answer [1].")
        self.assertEqual(result.mode, "fast")
        self.assertEqual(result.confidence, "high")

    def test_synthesize_rejects_uncited_model_answer(self) -> None:
        with patch("scripts.router._chat_ollama", return_value="Grounded answer without citation."):
            result = synthesize_answer_result(
                "What is the project alpha goal?",
                [source("Project Alpha goal is grounded answers with citations.")],
                mode="fast",
            )

        self.assertEqual(result.answer, ABSTENTION_MESSAGE)
        self.assertEqual(result.mode, "none")
        self.assertEqual(result.confidence, "low")


if __name__ == "__main__":
    unittest.main()
