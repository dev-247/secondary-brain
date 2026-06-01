from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.audit import audit_wiki


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


if __name__ == "__main__":
    unittest.main()
