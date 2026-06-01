from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from scripts.config import GRAPH_DB_PATH, QDRANT_COLLECTION
from scripts.qdrant_setup import get_client


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


@dataclass(frozen=True)
class EntityCandidate:
    entity_type: str
    name: str


@dataclass(frozen=True)
class RelationshipCandidate:
    subject: str
    predicate: str
    object: str
    object_type: str
    source_path: str
    chunk_index: int
    evidence: str


@dataclass(frozen=True)
class GraphCandidates:
    entities: list[EntityCandidate]
    relationships: list[RelationshipCandidate]


RELATIONSHIP_PATTERNS = (
    ("uses", re.compile(r"\b(Project\s+[A-Z][A-Za-z0-9-]*)\s+uses\s+([A-Z][A-Za-z0-9-]*(?:\s+[A-Z][A-Za-z0-9-]*){0,4})\b")),
    (
        "depends_on",
        re.compile(
            r"\b(Project\s+[A-Z][A-Za-z0-9-]*)\s+depends\s+on\s+([A-Z][A-Za-z0-9-]*(?:\s+[A-Z][A-Za-z0-9-]*){0,4})\b"
        ),
    ),
)


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def _normalize_predicate(predicate: str) -> str:
    return "_".join(predicate.lower().split())


def _clean_candidate_name(name: str) -> str:
    return name.strip().rstrip(".,;:")


def _sentence_for_match(text: str, start: int, end: int) -> str:
    sentence_start = text.rfind(".", 0, start) + 1
    sentence_end = text.find(".", end)
    if sentence_end == -1:
        sentence_end = len(text)
    else:
        sentence_end += 1
    return " ".join(text[sentence_start:sentence_end].split())


def _dedupe_entities(entities: list[EntityCandidate]) -> list[EntityCandidate]:
    seen: set[tuple[str, str]] = set()
    deduped: list[EntityCandidate] = []
    type_order = {"project": 0, "date": 1, "person": 2, "topic": 3}
    for entity in sorted(
        entities,
        key=lambda item: (type_order.get(item.entity_type, 99), _normalize_name(item.name)),
    ):
        key = (entity.entity_type, _normalize_name(entity.name))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entity)
    return deduped


def extract_graph_candidates(chunk: dict[str, object]) -> GraphCandidates:
    content = str(chunk.get("content", ""))
    source_path = str(chunk.get("path", ""))
    chunk_index = int(chunk.get("chunk_index", 0))
    entities: list[EntityCandidate] = []
    relationships: list[RelationshipCandidate] = []

    for match in re.finditer(r"\bProject\s+[A-Z][A-Za-z0-9-]*\b", content):
        entities.append(EntityCandidate("project", _clean_candidate_name(match.group(0))))

    for match in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", content):
        entities.append(EntityCandidate("date", match.group(0)))

    for predicate, pattern in RELATIONSHIP_PATTERNS:
        for match in pattern.finditer(content):
            subject = _clean_candidate_name(match.group(1))
            related_topic = _clean_candidate_name(match.group(2))
            if related_topic.startswith("Project "):
                object_type = "project"
            else:
                object_type = "topic"
            entities.append(EntityCandidate("project", subject))
            entities.append(EntityCandidate(object_type, related_topic))
            relationships.append(
                RelationshipCandidate(
                    subject=subject,
                    predicate=predicate,
                    object=related_topic,
                    object_type=object_type,
                    source_path=source_path,
                    chunk_index=chunk_index,
                    evidence=_sentence_for_match(content, match.start(), match.end()),
                )
            )

    return GraphCandidates(
        entities=_dedupe_entities(entities),
        relationships=relationships,
    )


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


def relationships_for_entity(
    db_path: Path = GRAPH_DB_PATH,
    name: str = "",
) -> list[GraphRelationship]:
    init_graph_db(db_path)
    normalized_name = _normalize_name(name)
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
            WHERE subject.normalized_name = ?
               OR object.normalized_name = ?
            ORDER BY
                CASE WHEN subject.normalized_name = ? THEN 0 ELSE 1 END,
                relationship.source_path,
                relationship.chunk_index,
                relationship.id
            """,
            (normalized_name, normalized_name, normalized_name),
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


def store_graph_candidates(
    db_path: Path = GRAPH_DB_PATH,
    candidates: GraphCandidates | None = None,
) -> dict[str, int]:
    if candidates is None:
        return {"entities": 0, "relationships": 0}

    entity_ids: dict[tuple[str, str], int] = {}
    for entity in candidates.entities:
        entity_id = upsert_entity(
            db_path,
            entity_type=entity.entity_type,
            name=entity.name,
        )
        entity_ids[(entity.entity_type, _normalize_name(entity.name))] = entity_id

    relationship_count = 0
    for relationship in candidates.relationships:
        subject_key = ("project", _normalize_name(relationship.subject))
        object_key = (relationship.object_type, _normalize_name(relationship.object))
        subject_id = entity_ids.get(subject_key)
        if subject_id is None:
            subject_id = upsert_entity(db_path, entity_type="project", name=relationship.subject)
        object_id = entity_ids.get(object_key)
        if object_id is None:
            object_id = upsert_entity(
                db_path,
                entity_type=relationship.object_type,
                name=relationship.object,
            )
        add_relationship(
            db_path,
            subject_id=subject_id,
            predicate=relationship.predicate,
            object_id=object_id,
            source_path=relationship.source_path,
            chunk_index=relationship.chunk_index,
            evidence=relationship.evidence,
        )
        relationship_count += 1

    return {
        "entities": len(candidates.entities),
        "relationships": relationship_count,
    }


def extract_graph_from_chunks(
    chunks: list[dict[str, object]],
    *,
    db_path: Path = GRAPH_DB_PATH,
) -> dict[str, int]:
    total_entities = 0
    total_relationships = 0
    for chunk in chunks:
        candidates = extract_graph_candidates(chunk)
        stats = store_graph_candidates(db_path, candidates)
        total_entities += stats["entities"]
        total_relationships += stats["relationships"]

    return {
        "chunks": len(chunks),
        "entities": total_entities,
        "relationships": total_relationships,
    }


def indexed_chunks_from_qdrant(limit: int = 500) -> list[dict[str, object]]:
    points, _ = get_client().scroll(
        collection_name=QDRANT_COLLECTION,
        limit=limit,
        with_payload=True,
    )
    chunks: list[dict[str, object]] = []
    for point in points:
        payload = point.payload or {}
        chunks.append(
            {
                "path": str(payload.get("path", "")),
                "chunk_index": int(payload.get("chunk_index", 0)),
                "content": str(payload.get("content", "")),
            }
        )
    return chunks
