from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CURRENT_INDEX_VERSION = 1
DEFAULT_PARSER_VERSION = "1"


@dataclass(frozen=True)
class FileFingerprint:
    sha256: str
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True)
class SourceRecord:
    path: str
    sha256: str
    size_bytes: int
    modified_ns: int
    chunks: int
    mime_type: str
    extension: str
    parser_name: str
    parser_version: str
    index_version: int


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_metadata_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS source_documents (
                path TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_ns INTEGER NOT NULL,
                chunks INTEGER NOT NULL,
                mime_type TEXT NOT NULL DEFAULT '',
                extension TEXT NOT NULL DEFAULT '',
                parser_name TEXT NOT NULL DEFAULT '',
                parser_version TEXT NOT NULL DEFAULT '',
                index_version INTEGER NOT NULL DEFAULT 0,
                indexed_at TEXT NOT NULL
            )
            """
        )
        _add_column_if_missing(connection, "source_documents", "mime_type", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(connection, "source_documents", "extension", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(connection, "source_documents", "parser_name", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(connection, "source_documents", "parser_version", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(connection, "source_documents", "index_version", "INTEGER NOT NULL DEFAULT 0")


def compute_file_fingerprint(path: Path) -> FileFingerprint:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    stat = path.stat()
    return FileFingerprint(
        sha256=digest.hexdigest(),
        size_bytes=stat.st_size,
        modified_ns=stat.st_mtime_ns,
    )


def get_source_record(db_path: Path, relative_path: str) -> SourceRecord | None:
    init_metadata_db(db_path)
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT path, sha256, size_bytes, modified_ns, chunks,
                   mime_type, extension, parser_name, parser_version, index_version
            FROM source_documents
            WHERE path = ?
            """,
            (relative_path,),
        ).fetchone()

    if row is None:
        return None
    return SourceRecord(
        path=str(row[0]),
        sha256=str(row[1]),
        size_bytes=int(row[2]),
        modified_ns=int(row[3]),
        chunks=int(row[4]),
        mime_type=str(row[5]),
        extension=str(row[6]),
        parser_name=str(row[7]),
        parser_version=str(row[8]),
        index_version=int(row[9]),
    )


def list_source_records(db_path: Path) -> list[SourceRecord]:
    init_metadata_db(db_path)
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT path, sha256, size_bytes, modified_ns, chunks,
                   mime_type, extension, parser_name, parser_version, index_version
            FROM source_documents
            ORDER BY path
            """
        ).fetchall()

    return [
        SourceRecord(
            path=str(row[0]),
            sha256=str(row[1]),
            size_bytes=int(row[2]),
            modified_ns=int(row[3]),
            chunks=int(row[4]),
            mime_type=str(row[5]),
            extension=str(row[6]),
            parser_name=str(row[7]),
            parser_version=str(row[8]),
            index_version=int(row[9]),
        )
        for row in rows
    ]


def delete_source_record(db_path: Path, relative_path: str) -> None:
    init_metadata_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "DELETE FROM source_documents WHERE path = ?",
            (relative_path,),
        )


def source_needs_ingest(
    db_path: Path,
    relative_path: str,
    fingerprint: FileFingerprint,
) -> bool:
    record = get_source_record(db_path, relative_path)
    if record is None:
        return True
    return record.sha256 != fingerprint.sha256 or record.index_version != CURRENT_INDEX_VERSION


def mark_source_indexed(db_path: Path, record: SourceRecord) -> None:
    init_metadata_db(db_path)
    indexed_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO source_documents (
                path, sha256, size_bytes, modified_ns, chunks,
                mime_type, extension, parser_name, parser_version, index_version,
                indexed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                sha256 = excluded.sha256,
                size_bytes = excluded.size_bytes,
                modified_ns = excluded.modified_ns,
                chunks = excluded.chunks,
                mime_type = excluded.mime_type,
                extension = excluded.extension,
                parser_name = excluded.parser_name,
                parser_version = excluded.parser_version,
                index_version = excluded.index_version,
                indexed_at = excluded.indexed_at
            """,
            (
                record.path,
                record.sha256,
                record.size_bytes,
                record.modified_ns,
                record.chunks,
                record.mime_type,
                record.extension,
                record.parser_name,
                record.parser_version,
                record.index_version,
                indexed_at,
            ),
        )
