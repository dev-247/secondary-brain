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


if __name__ == "__main__":
    unittest.main()
