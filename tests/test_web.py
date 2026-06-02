from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.search import SearchResult
from scripts.web import (
    build_answer_payload,
    build_command_center_payload,
    build_graph_action_payload,
    build_ingest_action_payload,
    build_search_payload,
    build_status_payload,
    build_wiki_generate_action_payload,
    build_wiki_promote_action_payload,
    clear_action_history,
    clear_chat_history,
    get_action_history,
    get_chat_history,
    list_source_files,
    list_wiki_pages,
    record_action_history,
    record_chat_history,
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
        self.assertIn("Command Center", html)
        self.assertIn("Next actions", html)
        self.assertIn("Local memory map", html)
        self.assertIn('class="action-link"', html)
        self.assertIn('href="#ask"', html)
        self.assertIn("table-layout: fixed", html)
        self.assertIn("overflow-wrap: anywhere", html)
        self.assertIn("Ask", html)
        self.assertIn("Chat history", html)
        self.assertIn("Ingestion", html)
        self.assertIn("Search", html)
        self.assertIn("Sources", html)
        self.assertIn("Wiki", html)
        self.assertIn("Graph", html)
        self.assertIn("Project Alpha", html)

    def test_build_command_center_payload_warns_for_review_queue(self) -> None:
        payload = build_command_center_payload(
            status={
                "qdrant_ready": True,
                "qdrant": "local",
                "vault_files": 2,
                "wiki_pages": 1,
                "graph_relationships": 4,
            },
            wiki_pages=[
                {
                    "path": "drafts/project-alpha.md",
                    "title": "Project Alpha",
                    "review_status": "draft",
                }
            ],
            chat_history=[
                {
                    "question": "What is alpha?",
                    "answer": "Alpha is local.",
                    "mode": "fast",
                    "confidence": "high",
                }
            ],
            action_history=[
                {
                    "name": "ingest",
                    "status": "ok",
                    "message": "Ingested 3 chunks.",
                }
            ],
        )

        self.assertEqual(payload["readiness"], "warning")
        self.assertIn("Review 1 wiki draft.", payload["next_actions"])
        self.assertIn(
            {"label": "Review 1 wiki draft.", "href": "#wiki"},
            payload["action_items"],
        )
        self.assertEqual(payload["review_queue"][0]["path"], "drafts/project-alpha.md")

    def test_build_command_center_payload_needs_attention_when_core_is_down(self) -> None:
        payload = build_command_center_payload(
            status={
                "qdrant_ready": False,
                "qdrant": "down",
                "vault_files": 0,
                "wiki_pages": 0,
                "graph_relationships": 0,
            },
            wiki_pages=[],
            chat_history=[],
            action_history=[],
        )

        self.assertEqual(payload["readiness"], "needs_attention")
        self.assertLess(payload["score"], 60)
        self.assertIn("Start or repair Qdrant before asking knowledge questions.", payload["next_actions"])
        self.assertIn(
            {"label": "Build graph memory after ingestion.", "href": "#operations"},
            payload["action_items"],
        )

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

    def test_chat_history_persists_in_activity_db(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "activity.sqlite"

            record_chat_history(
                "What is Project Alpha?",
                "Project Alpha keeps notes local [1].",
                "fast",
                "high",
                db_path=db_path,
            )
            history = get_chat_history(db_path=db_path)

        self.assertEqual(history[0]["question"], "What is Project Alpha?")
        self.assertEqual(history[0]["confidence"], "high")

    def test_validate_web_bind_requires_token_for_non_local_host(self) -> None:
        validate_web_bind("127.0.0.1", "")
        validate_web_bind("0.0.0.0", "secret-token")

        with self.assertRaises(ValueError):
            validate_web_bind("0.0.0.0", "")

    def test_build_ingest_action_payload_returns_ingest_stats(self) -> None:
        clear_action_history()
        with patch("scripts.web.ingest_vault") as ingest:
            ingest.return_value = {
                "files": 2,
                "chunks": 4,
                "skipped": 1,
                "deleted": 0,
                "failed": 0,
                "failed_files": [],
            }

            payload = build_ingest_action_payload()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["stats"]["chunks"], 4)
        self.assertEqual(payload["message"], "Ingested 4 chunks from 2 files.")
        self.assertEqual(get_action_history()[0]["name"], "ingest")

    def test_action_history_persists_in_activity_db(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "activity.sqlite"

            record_action_history(
                "graph-build",
                "ok",
                "Built graph from 1 chunks with 1 relationships.",
                db_path=db_path,
            )
            history = get_action_history(db_path=db_path)

        self.assertEqual(history[0]["name"], "graph-build")
        self.assertEqual(history[0]["status"], "ok")

    def test_build_graph_action_payload_returns_graph_stats(self) -> None:
        with (
            patch("scripts.web.indexed_chunks_from_qdrant", return_value=[{"content": "Project Alpha uses Local First AI."}]),
            patch("scripts.web.extract_graph_from_chunks", return_value={"chunks": 1, "entities": 2, "relationships": 1}),
        ):
            payload = build_graph_action_payload(limit=20)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["stats"]["relationships"], 1)
        self.assertEqual(payload["message"], "Built graph from 1 chunks with 1 relationships.")

    def test_build_wiki_generate_action_payload_writes_draft(self) -> None:
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
            patch("scripts.web.write_wiki_draft") as write_draft,
        ):
            write_draft.return_value = Path("/tmp/wiki/drafts/project-alpha.md")
            payload = build_wiki_generate_action_payload("Project Alpha", limit=3)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["path"], "/tmp/wiki/drafts/project-alpha.md")
        self.assertEqual(payload["message"], "Generated draft wiki page for Project Alpha.")

    def test_build_wiki_promote_action_payload_promotes_draft(self) -> None:
        with patch("scripts.web.promote_wiki_draft") as promote:
            promote.return_value = Path("/tmp/wiki/project-alpha.md")
            payload = build_wiki_promote_action_payload("project-alpha", reviewer="Vasu")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["path"], "/tmp/wiki/project-alpha.md")
        self.assertEqual(payload["message"], "Promoted project-alpha to reviewed wiki page.")


if __name__ == "__main__":
    unittest.main()
