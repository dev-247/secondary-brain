from __future__ import annotations

import unittest

from scripts.search import SearchResult, diagnostic_rows


class SearchDiagnosticsTests(unittest.TestCase):
    def test_diagnostic_rows_include_rank_score_citation_and_preview(self) -> None:
        rows = diagnostic_rows(
            [
                SearchResult(
                    content="This is a long source chunk that should be shortened for display.",
                    filename="note.md",
                    path="note.md",
                    heading="Ideas",
                    chunk_index=3,
                    score=0.812345,
                    fused_score=0.7,
                    lexical_score=0.45,
                )
            ],
            preview_chars=24,
        )

        self.assertEqual(
            rows,
            [
                {
                    "rank": "1",
                    "score": "0.8123",
                    "fused_score": "0.7000",
                    "lexical_score": "0.4500",
                    "path": "note.md",
                    "heading": "Ideas",
                    "chunk": "3",
                    "citation": "note.md (note.md#Ideas, chunk 3)",
                    "preview": "This is a long source...",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
