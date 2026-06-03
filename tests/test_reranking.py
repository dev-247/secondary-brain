from __future__ import annotations

import unittest

from scripts.search import LexicalOnlyReranker, WeightedLexicalReranker, SearchResult, rerank


def result(path: str, content: str, score: float) -> SearchResult:
    return SearchResult(
        content=content,
        filename=path,
        path=path,
        heading="Doc",
        chunk_index=0,
        score=score,
        fused_score=score,
    )


class RerankingTests(unittest.TestCase):
    def test_weighted_lexical_reranker_preserves_fused_and_lexical_scores(self) -> None:
        results = [
            result("semantic.md", "broad conceptual match", 0.9),
            result("keyword.md", "alpha beta exact match", 0.6),
        ]

        ranked = rerank("alpha beta", results, limit=2, strategy=WeightedLexicalReranker())

        self.assertEqual([item.path for item in ranked], ["semantic.md", "keyword.md"])
        self.assertEqual(ranked[0].fused_score, 0.9)
        self.assertEqual(ranked[1].lexical_score, 1.0)

    def test_lexical_only_reranker_can_prioritize_exact_keyword_matches(self) -> None:
        results = [
            result("semantic.md", "broad conceptual match", 0.9),
            result("keyword.md", "alpha beta exact match", 0.1),
        ]

        ranked = rerank("alpha beta", results, limit=2, strategy=LexicalOnlyReranker())

        self.assertEqual([item.path for item in ranked], ["keyword.md", "semantic.md"])
        self.assertEqual(ranked[0].score, 1.0)

    def test_definition_query_prioritizes_matching_document_intro(self) -> None:
        intro = SearchResult(
            content="# Dependency Injection in Flutter\n\nGetIt provides a DI container.",
            filename="DI.md",
            path="DI.md",
            heading="Dependency Injection in Flutter",
            chunk_index=0,
            score=0.31,
            fused_score=0.31,
        )
        later = SearchResult(
            content="DI in Clean Architecture ties presentation, domain, and data layers.",
            filename="DI.md",
            path="DI.md",
            heading="DI in Clean Architecture Layers",
            chunk_index=6,
            score=0.58,
            fused_score=0.58,
        )

        ranked = rerank("what is DI?", [later, intro], limit=2, strategy=WeightedLexicalReranker())

        self.assertEqual(ranked[0].chunk_index, 0)
        self.assertGreater(ranked[0].score, ranked[1].score)


if __name__ == "__main__":
    unittest.main()
