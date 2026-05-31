from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.metadata import (
    SourceRecord,
    compute_file_fingerprint,
    delete_source_record,
    get_source_record,
    init_metadata_db,
    list_source_records,
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

    def test_list_and_delete_source_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "metadata.sqlite"
            init_metadata_db(db_path)
            mark_source_indexed(
                db_path,
                SourceRecord(
                    path="alpha.md",
                    sha256="alpha",
                    size_bytes=10,
                    modified_ns=100,
                    chunks=1,
                ),
            )
            mark_source_indexed(
                db_path,
                SourceRecord(
                    path="beta.md",
                    sha256="beta",
                    size_bytes=20,
                    modified_ns=200,
                    chunks=2,
                ),
            )

            self.assertEqual(
                [record.path for record in list_source_records(db_path)],
                ["alpha.md", "beta.md"],
            )

            delete_source_record(db_path, "alpha.md")

            self.assertEqual(
                [record.path for record in list_source_records(db_path)],
                ["beta.md"],
            )


if __name__ == "__main__":
    unittest.main()
