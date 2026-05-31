from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qdrant_client import QdrantClient

from scripts.ingest import ingest_vault
from scripts.metadata import CURRENT_INDEX_VERSION, get_source_record
from scripts.search import hybrid_search


def fake_embedding(_: str) -> list[float]:
    return [1.0] + [0.0] * 767


class IncrementalIngestTests(unittest.TestCase):
    def run_isolated_ingest(self, vault: Path, metadata: Path, client: QdrantClient) -> dict[str, int]:
        with patch("scripts.ingest.embed_text", side_effect=fake_embedding):
            with patch("scripts.search.embed_text", side_effect=fake_embedding):
                with patch("scripts.qdrant_setup.QDRANT_COLLECTION", "test_incremental"):
                    with patch("scripts.ingest.QDRANT_COLLECTION", "test_incremental"):
                        with patch("scripts.search.QDRANT_COLLECTION", "test_incremental"):
                            with patch("scripts.qdrant_setup.get_client", return_value=client):
                                with patch("scripts.ingest.get_client", return_value=client):
                                    with patch("scripts.search.get_client", return_value=client):
                                        return ingest_vault(vault, metadata_path=metadata)

    def test_second_ingest_skips_unchanged_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            metadata = root / "metadata.sqlite"
            qdrant_path = root / "qdrant"
            client = QdrantClient(path=str(qdrant_path))
            vault.mkdir()
            (vault / "alpha.md").write_text("# Alpha\n\nStable content.", encoding="utf-8")

            first = self.run_isolated_ingest(vault, metadata, client)
            second = self.run_isolated_ingest(vault, metadata, client)

        self.assertEqual(first["files"], 1)
        self.assertEqual(first["chunks"], 1)
        self.assertEqual(first["skipped"], 0)
        self.assertEqual(second["files"], 1)
        self.assertEqual(second["chunks"], 0)
        self.assertEqual(second["skipped"], 1)

    def test_changed_file_removes_stale_chunks_before_reindexing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            metadata = root / "metadata.sqlite"
            qdrant_path = root / "qdrant"
            client = QdrantClient(path=str(qdrant_path))
            vault.mkdir()
            note = vault / "alpha.md"
            note.write_text(
                "# Alpha\n\n"
                + ("First version with stale beta content.\n\n" * 120)
                + "BetaOnlyToken should disappear after reindex.",
                encoding="utf-8",
            )

            first = self.run_isolated_ingest(vault, metadata, client)
            note.write_text("# Alpha\n\nFresh replacement only.", encoding="utf-8")
            second = self.run_isolated_ingest(vault, metadata, client)

            with patch("scripts.search.embed_text", side_effect=fake_embedding):
                with patch("scripts.search.QDRANT_COLLECTION", "test_incremental"):
                    with patch("scripts.search.get_client", return_value=client):
                        results = hybrid_search("BetaOnlyToken", limit=5)

        self.assertGreater(first["chunks"], 1)
        self.assertEqual(second["chunks"], 1)
        self.assertTrue(all("BetaOnlyToken" not in result.content for result in results))

    def test_deleted_file_removes_indexed_chunks_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            metadata = root / "metadata.sqlite"
            qdrant_path = root / "qdrant"
            client = QdrantClient(path=str(qdrant_path))
            vault.mkdir()
            note = vault / "alpha.md"
            note.write_text("# Alpha\n\nDeleteOnlyToken should disappear.", encoding="utf-8")

            first = self.run_isolated_ingest(vault, metadata, client)
            note.unlink()
            second = self.run_isolated_ingest(vault, metadata, client)

            with patch("scripts.search.embed_text", side_effect=fake_embedding):
                with patch("scripts.search.QDRANT_COLLECTION", "test_incremental"):
                    with patch("scripts.search.get_client", return_value=client):
                        results = hybrid_search("DeleteOnlyToken", limit=5)

        self.assertEqual(first["chunks"], 1)
        self.assertEqual(second["files"], 0)
        self.assertEqual(second["deleted"], 1)
        self.assertTrue(all("DeleteOnlyToken" not in result.content for result in results))

    def test_failed_file_does_not_stop_remaining_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            metadata = root / "metadata.sqlite"
            qdrant_path = root / "qdrant"
            client = QdrantClient(path=str(qdrant_path))
            vault.mkdir()
            good = vault / "good.md"
            bad = vault / "bad.md"
            good.write_text("# Good\n\nThis file should ingest.", encoding="utf-8")
            bad.write_text("# Bad\n\nThis file should fail.", encoding="utf-8")

            def extract_or_fail(path: Path) -> tuple[str, str]:
                if path.name == "bad.md":
                    raise ValueError("broken parse")
                return "Good", path.read_text(encoding="utf-8")

            with patch("scripts.ingest._extract_text", side_effect=extract_or_fail):
                stats = self.run_isolated_ingest(vault, metadata, client)

        self.assertEqual(stats["files"], 2)
        self.assertEqual(stats["chunks"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["failed_files"], [{"path": "bad.md", "error": "broken parse"}])

    def test_ingest_records_richer_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            metadata = root / "metadata.sqlite"
            qdrant_path = root / "qdrant"
            client = QdrantClient(path=str(qdrant_path))
            vault.mkdir()
            (vault / "alpha.md").write_text("# Alpha\n\nMetadata content.", encoding="utf-8")

            self.run_isolated_ingest(vault, metadata, client)
            record = get_source_record(metadata, "alpha.md")

        self.assertIsNotNone(record)
        self.assertEqual(record.mime_type, "text/markdown")
        self.assertEqual(record.extension, ".md")
        self.assertEqual(record.parser_name, "direct")
        self.assertEqual(record.parser_version, "1")
        self.assertEqual(record.index_version, CURRENT_INDEX_VERSION)


if __name__ == "__main__":
    unittest.main()
