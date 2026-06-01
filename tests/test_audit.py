from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from scripts.audit import audit_wiki, detect_contradiction_candidates
from scripts.metadata import (
    CURRENT_INDEX_VERSION,
    SourceRecord,
    mark_source_indexed,
)


class AuditTests(unittest.TestCase):
    def test_audit_counts_drafts_and_reviewed_pages_separately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drafts = root / "drafts"
            drafts.mkdir()
            (drafts / "alpha.md").write_text(
                "---\nreview_status: draft\n---\n# Alpha\n",
                encoding="utf-8",
            )
            (root / "reviewed.md").write_text(
                "---\nreview_status: reviewed\n---\n# Reviewed\n",
                encoding="utf-8",
            )

            with patch("scripts.audit.check_qdrant_health", return_value=False):
                report = audit_wiki(root)

        self.assertEqual(report["wiki_files"], 2)
        self.assertEqual(report["draft_files"], ["drafts/alpha.md"])
        self.assertEqual(report["reviewed_files"], ["reviewed.md"])
        self.assertEqual(report["draft_count"], 1)
        self.assertEqual(report["reviewed_count"], 1)

    def test_audit_suggests_newer_indexed_sources_for_stale_topics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "wiki"
            root.mkdir()
            metadata_path = Path(directory) / "metadata.sqlite"
            wiki_page = root / "project-alpha.md"
            wiki_page.write_text("# Project Alpha\n", encoding="utf-8")
            old_modified_ns = 1_700_000_000_000_000_000
            os.utime(wiki_page, ns=(old_modified_ns, old_modified_ns))
            mark_source_indexed(
                metadata_path,
                SourceRecord(
                    path="project-alpha-roadmap.md",
                    sha256="alpha",
                    size_bytes=100,
                    modified_ns=old_modified_ns + 10_000,
                    chunks=2,
                    mime_type="text/markdown",
                    extension=".md",
                    parser_name="direct",
                    parser_version="1",
                    index_version=CURRENT_INDEX_VERSION,
                ),
            )
            mark_source_indexed(
                metadata_path,
                SourceRecord(
                    path="unrelated-health.md",
                    sha256="health",
                    size_bytes=100,
                    modified_ns=old_modified_ns + 20_000,
                    chunks=1,
                    mime_type="text/markdown",
                    extension=".md",
                    parser_name="direct",
                    parser_version="1",
                    index_version=CURRENT_INDEX_VERSION,
                ),
            )

            with patch("scripts.audit.check_qdrant_health", return_value=False):
                report = audit_wiki(root, metadata_path=metadata_path)

        self.assertEqual(
            report["refresh_suggestions"],
            [
                {
                    "wiki": "project-alpha.md",
                    "sources": ["project-alpha-roadmap.md"],
                }
            ],
        )

    def test_detects_contradiction_candidates_from_related_chunks(self) -> None:
        candidates = detect_contradiction_candidates(
            [
                {
                    "path": "project-alpha.md",
                    "content": "For Project Alpha, the cloud LLM is required for deep answers.",
                },
                {
                    "path": "project-alpha-review.md",
                    "content": "For Project Alpha, the cloud LLM is optional for deep answers.",
                },
                {
                    "path": "health.md",
                    "content": "A morning walk is optional for this routine.",
                },
            ]
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0]["sources"],
            ["project-alpha.md", "project-alpha-review.md"],
        )
        self.assertEqual(candidates[0]["signals"], ["required", "optional"])
        self.assertIn("project", candidates[0]["shared_terms"])


if __name__ == "__main__":
    unittest.main()
