from __future__ import annotations

import unittest

from scripts.search import SearchResult, format_citation


class CitationTests(unittest.TestCase):
    def test_format_citation_prefers_page_when_available(self) -> None:
        result = SearchResult(
            content="Source content",
            filename="paper.pdf",
            path="paper.pdf",
            heading="Findings",
            chunk_index=2,
            score=0.9,
            page_start=4,
            page_end=6,
        )

        self.assertEqual(format_citation(result), "paper.pdf (paper.pdf, pages 4-6, chunk 2)")

    def test_format_citation_uses_heading_without_page(self) -> None:
        result = SearchResult(
            content="Source content",
            filename="note.md",
            path="note.md",
            heading="Findings",
            chunk_index=1,
            score=0.9,
        )

        self.assertEqual(format_citation(result), "note.md (note.md#Findings, chunk 1)")


if __name__ == "__main__":
    unittest.main()
