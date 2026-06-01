from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.search import SearchResult
from scripts.wiki import build_wiki_draft, slugify, write_wiki_draft


def result(content: str, path: str = "note.md", heading: str = "Ideas") -> SearchResult:
    return SearchResult(
        content=content,
        filename=path,
        path=path,
        heading=heading,
        chunk_index=0,
        score=0.8,
    )


class WikiTests(unittest.TestCase):
    def test_slugify_normalizes_topic_for_filename(self) -> None:
        self.assertEqual(slugify("Project Alpha: Local-First AI!"), "project-alpha-local-first-ai")

    def test_build_wiki_draft_marks_ai_draft_and_cites_sources(self) -> None:
        draft = build_wiki_draft(
            "Project Alpha",
            [
                result("Project Alpha keeps documents local by default."),
                result("Cloud models are optional deep reasoning fallback.", "cloud.md", "Routing"),
            ],
        )

        self.assertIn("review_status: draft", draft)
        self.assertIn("generated_by: second-brain", draft)
        self.assertIn("# Project Alpha", draft)
        self.assertIn("- Project Alpha keeps documents local by default. [1]", draft)
        self.assertIn("## Sources", draft)
        self.assertIn("[1] note.md (note.md#Ideas, chunk 0)", draft)
        self.assertIn("[2] cloud.md (cloud.md#Routing, chunk 0)", draft)

    def test_write_wiki_draft_creates_drafts_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_wiki_draft(
                "Project Alpha",
                [result("Project Alpha keeps documents local by default.")],
                wiki_root=Path(directory),
            )

            self.assertEqual(path.name, "project-alpha.md")
            self.assertEqual(path.parent.name, "drafts")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
