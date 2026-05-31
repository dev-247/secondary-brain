from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qdrant_client import QdrantClient

from scripts.ingest import ingest_vault


def fake_embedding(_: str) -> list[float]:
    return [1.0] + [0.0] * 767


class IncrementalIngestTests(unittest.TestCase):
    def test_second_ingest_skips_unchanged_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            metadata = root / "metadata.sqlite"
            qdrant_path = root / "qdrant"
            client = QdrantClient(path=str(qdrant_path))
            vault.mkdir()
            (vault / "alpha.md").write_text("# Alpha\n\nStable content.", encoding="utf-8")

            with patch("scripts.ingest.embed_text", side_effect=fake_embedding):
                with patch("scripts.qdrant_setup.QDRANT_COLLECTION", "test_incremental"):
                    with patch("scripts.ingest.QDRANT_COLLECTION", "test_incremental"):
                        with patch("scripts.qdrant_setup.get_client", return_value=client):
                            with patch("scripts.ingest.get_client", return_value=client):
                                first = ingest_vault(vault, metadata_path=metadata)
                                second = ingest_vault(vault, metadata_path=metadata)

        self.assertEqual(first["files"], 1)
        self.assertEqual(first["chunks"], 1)
        self.assertEqual(first["skipped"], 0)
        self.assertEqual(second["files"], 1)
        self.assertEqual(second["chunks"], 0)
        self.assertEqual(second["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
