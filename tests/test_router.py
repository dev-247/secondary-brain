from __future__ import annotations

import unittest

from unittest.mock import patch

from scripts.router import (
    ABSTENTION_MESSAGE,
    assess_source_coverage,
    choose_mode,
    normalize_answer,
    polish_answer,
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

    def test_source_coverage_uses_heading_and_filename_for_acronyms(self) -> None:
        coverage = assess_source_coverage(
            "What is DI?",
            [
                SearchResult(
                    content="GetIt provides a simple service locator container.",
                    filename="DI.md",
                    path="DI.md",
                    heading="Dependency Injection in Flutter",
                    chunk_index=0,
                    score=0.7,
                )
            ],
        )

        self.assertTrue(coverage.supported)

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

    def test_polish_answer_moves_standalone_citation_to_previous_sentence(self) -> None:
        answer = "Dependency Injection keeps components loosely coupled.\n\n[1]"

        polished = polish_answer(answer)

        self.assertEqual(polished, "Dependency Injection keeps components loosely coupled. [1]")

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

    def test_synthesize_polishes_model_answer_before_returning_it(self) -> None:
        with patch("scripts.router._chat_ollama", return_value="Grounded answer.\n\n[1]"):
            result = synthesize_answer_result(
                "What is the project alpha goal?",
                [source("Project Alpha goal is grounded answers with citations.")],
                mode="fast",
            )

        self.assertEqual(result.answer, "Grounded answer. [1]")
        self.assertEqual(result.mode, "fast")

    def test_synthesize_uses_definition_fallback_when_model_abstains(self) -> None:
        with patch("scripts.router._chat_ollama", return_value=ABSTENTION_MESSAGE):
            result = synthesize_answer_result(
                "what is DI",
                [
                    SearchResult(
                        content="GetIt provides a simple, fast service locator/DI container[pub.dev](https://pub.dev/packages/get_it). Combined with injectable, boilerplate is generated.",
                        filename="DI.md",
                        path="DI.md",
                        heading="Dependency Injection in Flutter",
                        chunk_index=0,
                        score=0.7,
                        lexical_score=0.5,
                    )
                ],
                mode="fast",
            )

        self.assertIn("Dependency Injection in Flutter", result.answer)
        self.assertIn("[1]", result.answer)
        self.assertNotIn("# Dependency Injection", result.answer)
        self.assertNotIn("pub.dev", result.answer)
        self.assertNotIn("Combined with", result.answer)
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

    def test_synthesize_uses_definition_fallback_for_uncited_model_answer(self) -> None:
        with patch("scripts.router._chat_ollama", return_value="DI means Dependency Injection."):
            result = synthesize_answer_result(
                "what is DI",
                [
                    SearchResult(
                        content="GetIt provides a simple, fast service locator/DI container.",
                        filename="DI.md",
                        path="DI.md",
                        heading="Dependency Injection in Flutter",
                        chunk_index=0,
                        score=0.7,
                        lexical_score=0.5,
                    )
                ],
                mode="fast",
            )

        self.assertIn("Dependency Injection in Flutter", result.answer)
        self.assertIn("[1]", result.answer)
        self.assertEqual(result.mode, "fast")


if __name__ == "__main__":
    unittest.main()
