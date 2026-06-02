from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.web import build_status_payload, list_wiki_pages, render_dashboard


class WebTests(unittest.TestCase):
    def test_build_status_payload_reports_project_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            wiki = root / "wiki"
            vault.mkdir()
            wiki.mkdir()
            (vault / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (wiki / "project-alpha.md").write_text("# Project Alpha\n", encoding="utf-8")

            with patch("scripts.web.check_qdrant_health", return_value=True):
                payload = build_status_payload(vault_root=vault, wiki_root=wiki)

        self.assertTrue(payload["qdrant_ready"])
        self.assertEqual(payload["vault_files"], 1)
        self.assertEqual(payload["wiki_pages"], 1)

    def test_list_wiki_pages_reads_title_and_review_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wiki = Path(directory)
            (wiki / "project-alpha.md").write_text(
                "---\n"
                "title: Project Alpha\n"
                "review_status: reviewed\n"
                "---\n"
                "# Project Alpha\n",
                encoding="utf-8",
            )

            pages = list_wiki_pages(wiki_root=wiki)

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["path"], "project-alpha.md")
        self.assertEqual(pages[0]["title"], "Project Alpha")
        self.assertEqual(pages[0]["review_status"], "reviewed")

    def test_render_dashboard_contains_product_sections(self) -> None:
        html = render_dashboard(
            status={
                "qdrant_ready": True,
                "qdrant": "local",
                "vault_files": 2,
                "wiki_pages": 1,
                "graph_relationships": 3,
            },
            wiki_pages=[
                {
                    "path": "project-alpha.md",
                    "title": "Project Alpha",
                    "review_status": "reviewed",
                }
            ],
        )

        self.assertIn("Second Brain", html)
        self.assertIn("Ingestion", html)
        self.assertIn("Search", html)
        self.assertIn("Wiki", html)
        self.assertIn("Graph", html)
        self.assertIn("Project Alpha", html)


if __name__ == "__main__":
    unittest.main()
