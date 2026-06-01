from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.config import GRAPH_DB_PATH


@dataclass(frozen=True)
class GraphEntity:
    id: int
    entity_type: str
    name: str
    normalized_name: str


@dataclass(frozen=True)
class GraphRelationship:
    id: int
    subject_id: int
    subject_name: str
    predicate: str
    object_id: int
    object_name: str
    source_path: str
    chunk_index: int
    evidence: str


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def _normalize_predicate(predicate: str) -> str:
    return "_".join(predicate.lower().split())


def init_graph_db(db_path: Path = GRAPH_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(entity_type, normalized_name)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                predicate TEXT NOT NULL,
                object_id INTEGER NOT NULL,
                source_path TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                evidence TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(subject_id) REFERENCES graph_entities(id),
                FOREIGN KEY(object_id) REFERENCES graph_entities(id),
                UNIQUE(subject_id, predicate, object_id, source_path, chunk_index)
            )
            """
        )


def upsert_entity(
    db_path: Path = GRAPH_DB_PATH,
    *,
    entity_type: str,
    name: str,
) -> int:
    init_graph_db(db_path)
    clean_type = _normalize_predicate(entity_type)
    clean_name = " ".join(name.split())
    normalized_name = _normalize_name(name)
    timestamp = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO graph_entities (
                entity_type, name, normalized_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entity_type, normalized_name) DO UPDATE SET
                updated_at = excluded.updated_at
            """,
            (clean_type, clean_name, normalized_name, timestamp, timestamp),
        )
        row = connection.execute(
            """
            SELECT id FROM graph_entities
            WHERE entity_type = ? AND normalized_name = ?
            """,
            (clean_type, normalized_name),
        ).fetchone()
    return int(row[0])


def get_entity(db_path: Path = GRAPH_DB_PATH, entity_id: int = 0) -> GraphEntity | None:
    init_graph_db(db_path)
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, entity_type, name, normalized_name
            FROM graph_entities
            WHERE id = ?
            """,
            (entity_id,),
        ).fetchone()

    if row is None:
        return None
    return GraphEntity(
        id=int(row[0]),
        entity_type=str(row[1]),
        name=str(row[2]),
        normalized_name=str(row[3]),
    )


def add_relationship(
    db_path: Path = GRAPH_DB_PATH,
    *,
    subject_id: int,
    predicate: str,
    object_id: int,
    source_path: str,
    chunk_index: int,
    evidence: str,
) -> int:
    init_graph_db(db_path)
    clean_predicate = _normalize_predicate(predicate)
    timestamp = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO graph_relationships (
                subject_id, predicate, object_id, source_path, chunk_index,
                evidence, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(subject_id, predicate, object_id, source_path, chunk_index)
            DO UPDATE SET
                evidence = excluded.evidence,
                updated_at = excluded.updated_at
            """,
            (
                subject_id,
                clean_predicate,
                object_id,
                source_path,
                chunk_index,
                evidence,
                timestamp,
                timestamp,
            ),
        )
        row = connection.execute(
            """
            SELECT id FROM graph_relationships
            WHERE subject_id = ?
              AND predicate = ?
              AND object_id = ?
              AND source_path = ?
              AND chunk_index = ?
            """,
            (subject_id, clean_predicate, object_id, source_path, chunk_index),
        ).fetchone()
    return int(row[0])


def list_relationships(db_path: Path = GRAPH_DB_PATH) -> list[GraphRelationship]:
    init_graph_db(db_path)
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                relationship.id,
                relationship.subject_id,
                subject.name,
                relationship.predicate,
                relationship.object_id,
                object.name,
                relationship.source_path,
                relationship.chunk_index,
                relationship.evidence
            FROM graph_relationships AS relationship
            JOIN graph_entities AS subject ON subject.id = relationship.subject_id
            JOIN graph_entities AS object ON object.id = relationship.object_id
            ORDER BY relationship.source_path, relationship.chunk_index, relationship.id
            """
        ).fetchall()

    return [
        GraphRelationship(
            id=int(row[0]),
            subject_id=int(row[1]),
            subject_name=str(row[2]),
            predicate=str(row[3]),
            object_id=int(row[4]),
            object_name=str(row[5]),
            source_path=str(row[6]),
            chunk_index=int(row[7]),
            evidence=str(row[8]),
        )
        for row in rows
    ]
