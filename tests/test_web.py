from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.search import SearchResult
from scripts.web import (
    build_answer_payload,
    build_search_payload,
    build_status_payload,
    clear_chat_history,
    get_chat_history,
    list_source_files,
    list_wiki_pages,
    read_source_file,
    render_dashboard,
    validate_web_bind,
)


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
            source_files=["alpha.md"],
        )

        self.assertIn("Second Brain", html)
        self.assertIn("Ask", html)
        self.assertIn("Chat history", html)
        self.assertIn("Ingestion", html)
        self.assertIn("Search", html)
        self.assertIn("Sources", html)
        self.assertIn("Wiki", html)
        self.assertIn("Graph", html)
        self.assertIn("Project Alpha", html)

    def test_build_search_payload_returns_citations(self) -> None:
        result = SearchResult(
            content="Project Alpha keeps notes local.",
            filename="alpha.md",
            path="alpha.md",
            heading="Overview",
            chunk_index=0,
            score=0.8,
        )
        with (
            patch("scripts.web.check_qdrant_health", return_value=True),
            patch("scripts.web.hybrid_search", return_value=[result]),
        ):
            payload = build_search_payload("Project Alpha", limit=3)

        self.assertEqual(payload["query"], "Project Alpha")
        self.assertEqual(payload["results"][0]["path"], "alpha.md")
        self.assertIn("alpha.md", payload["results"][0]["citation"])

    def test_list_and_read_source_files_stays_inside_vault(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (vault / "ignore.bin").write_text("binary-ish", encoding="utf-8")

            files = list_source_files(vault_root=vault)
            source = read_source_file("alpha.md", vault_root=vault)

            with self.assertRaises(ValueError):
                read_source_file("../secret.md", vault_root=vault)

        self.assertEqual(files, ["alpha.md"])
        self.assertEqual(source["content"], "# Alpha\n")

    def test_build_answer_payload_returns_answer_sources_and_history(self) -> None:
        clear_chat_history()
        result = SearchResult(
            content="Project Alpha keeps notes local.",
            filename="alpha.md",
            path="alpha.md",
            heading="Overview",
            chunk_index=0,
            score=0.8,
        )

        with (
            patch("scripts.web.check_qdrant_health", return_value=True),
            patch("scripts.web.hybrid_search", return_value=[result]),
            patch("scripts.web.synthesize_answer_result") as synthesize,
        ):
            synthesize.return_value.answer = "Project Alpha keeps notes local [1]."
            synthesize.return_value.mode = "fast"
            synthesize.return_value.confidence = "high"
            payload = build_answer_payload("What is Project Alpha?", limit=3)

        self.assertEqual(payload["answer"], "Project Alpha keeps notes local [1].")
        self.assertEqual(payload["mode"], "fast")
        self.assertEqual(payload["confidence"], "high")
        self.assertEqual(payload["sources"][0]["path"], "alpha.md")
        self.assertEqual(get_chat_history()[0]["question"], "What is Project Alpha?")

    def test_validate_web_bind_requires_token_for_non_local_host(self) -> None:
        validate_web_bind("127.0.0.1", "")
        validate_web_bind("0.0.0.0", "secret-token")

        with self.assertRaises(ValueError):
            validate_web_bind("0.0.0.0", "")


if __name__ == "__main__":
    unittest.main()
