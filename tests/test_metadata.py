from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.metadata import (
    SourceRecord,
    compute_file_fingerprint,
    get_source_record,
    init_metadata_db,
    mark_source_indexed,
    source_needs_ingest,
)


class MetadataTests(unittest.TestCase):
    def test_compute_file_fingerprint_changes_when_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            path.write_text("first version", encoding="utf-8")

            first = compute_file_fingerprint(path)
            path.write_text("second version", encoding="utf-8")
            second = compute_file_fingerprint(path)

        self.assertNotEqual(first.sha256, second.sha256)
        self.assertEqual(second.size_bytes, len("second version"))

    def test_source_needs_ingest_is_false_after_matching_record_is_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "metadata.sqlite"
            source = Path(directory) / "note.md"
            source.write_text("stable note", encoding="utf-8")
            init_metadata_db(db_path)

            fingerprint = compute_file_fingerprint(source)
            self.assertTrue(source_needs_ingest(db_path, "note.md", fingerprint))

            mark_source_indexed(
                db_path,
                SourceRecord(
                    path="note.md",
                    sha256=fingerprint.sha256,
                    size_bytes=fingerprint.size_bytes,
                    modified_ns=fingerprint.modified_ns,
                    chunks=2,
                ),
            )

            self.assertFalse(source_needs_ingest(db_path, "note.md", fingerprint))
            record = get_source_record(db_path, "note.md")
            self.assertIsNotNone(record)
            self.assertEqual(record.chunks, 2)


if __name__ == "__main__":
    unittest.main()
