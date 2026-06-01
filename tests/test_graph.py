from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.graph import (
    add_relationship,
    extract_graph_candidates,
    extract_graph_from_chunks,
    get_entity,
    init_graph_db,
    list_relationships,
    relationships_for_entity,
    store_graph_candidates,
    timeline_for_entity,
    upsert_entity,
)


class GraphTests(unittest.TestCase):
    def test_upsert_entity_reuses_same_normalized_entity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "graph.sqlite"
            init_graph_db(db_path)

            first = upsert_entity(db_path, entity_type="project", name="Project Alpha")
            second = upsert_entity(db_path, entity_type="project", name=" project alpha ")

            self.assertEqual(first, second)
            entity = get_entity(db_path, first)
            self.assertIsNotNone(entity)
            self.assertEqual(entity.name, "Project Alpha")
            self.assertEqual(entity.normalized_name, "project alpha")

    def test_add_relationship_links_entities_to_source_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "graph.sqlite"
            init_graph_db(db_path)

            project_id = upsert_entity(db_path, entity_type="project", name="Project Alpha")
            topic_id = upsert_entity(db_path, entity_type="topic", name="Local First AI")

            add_relationship(
                db_path,
                subject_id=project_id,
                predicate="uses",
                object_id=topic_id,
                source_path="project-alpha.md",
                chunk_index=2,
                evidence="Project Alpha uses local-first AI for private notes.",
            )

            relationships = list_relationships(db_path)

        self.assertEqual(len(relationships), 1)
        relationship = relationships[0]
        self.assertEqual(relationship.subject_name, "Project Alpha")
        self.assertEqual(relationship.predicate, "uses")
        self.assertEqual(relationship.object_name, "Local First AI")
        self.assertEqual(relationship.source_path, "project-alpha.md")
        self.assertEqual(relationship.chunk_index, 2)
        self.assertEqual(
            relationship.evidence,
            "Project Alpha uses local-first AI for private notes.",
        )

    def test_extract_graph_candidates_from_chunk_text(self) -> None:
        candidates = extract_graph_candidates(
            {
                "path": "project-alpha.md",
                "chunk_index": 3,
                "content": (
                    "Project Alpha uses Local First AI. "
                    "Project Alpha depends on Hybrid Retrieval. "
                    "Reviewed on 2026-06-01."
                ),
            }
        )

        self.assertEqual(
            [(entity.entity_type, entity.name) for entity in candidates.entities],
            [
                ("project", "Project Alpha"),
                ("date", "2026-06-01"),
                ("topic", "Hybrid Retrieval"),
                ("topic", "Local First AI"),
            ],
        )
        self.assertEqual(len(candidates.relationships), 2)
        self.assertEqual(candidates.relationships[0].subject, "Project Alpha")
        self.assertEqual(candidates.relationships[0].predicate, "uses")
        self.assertEqual(candidates.relationships[0].object, "Local First AI")
        self.assertEqual(candidates.relationships[0].source_path, "project-alpha.md")
        self.assertEqual(candidates.relationships[0].chunk_index, 3)

    def test_extract_graph_candidates_links_project_dates_for_timeline(self) -> None:
        candidates = extract_graph_candidates(
            {
                "path": "project-alpha.md",
                "chunk_index": 4,
                "content": "Project Alpha launched on 2026-06-01.",
            }
        )

        self.assertIn(("date", "2026-06-01"), [(entity.entity_type, entity.name) for entity in candidates.entities])
        self.assertEqual(len(candidates.relationships), 1)
        self.assertEqual(candidates.relationships[0].subject, "Project Alpha")
        self.assertEqual(candidates.relationships[0].predicate, "mentioned_on")
        self.assertEqual(candidates.relationships[0].object, "2026-06-01")
        self.assertEqual(candidates.relationships[0].object_type, "date")

    def test_store_graph_candidates_persists_entities_and_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "graph.sqlite"
            candidates = extract_graph_candidates(
                {
                    "path": "project-alpha.md",
                    "chunk_index": 0,
                    "content": "Project Alpha uses Local First AI.",
                }
            )

            stats = store_graph_candidates(db_path, candidates)
            relationships = list_relationships(db_path)

        self.assertEqual(stats, {"entities": 2, "relationships": 1})
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0].subject_name, "Project Alpha")
        self.assertEqual(relationships[0].predicate, "uses")
        self.assertEqual(relationships[0].object_name, "Local First AI")

    def test_extract_graph_from_chunks_combines_stats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "graph.sqlite"

            stats = extract_graph_from_chunks(
                [
                    {
                        "path": "project-alpha.md",
                        "chunk_index": 0,
                        "content": "Project Alpha uses Local First AI.",
                    },
                    {
                        "path": "project-alpha.md",
                        "chunk_index": 1,
                        "content": "Project Alpha depends on Hybrid Retrieval.",
                    },
                ],
                db_path=db_path,
            )
            relationships = list_relationships(db_path)

        self.assertEqual(stats, {"chunks": 2, "entities": 4, "relationships": 2})
        self.assertEqual(len(relationships), 2)

    def test_relationships_for_entity_returns_inbound_and_outbound_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "graph.sqlite"
            alpha_id = upsert_entity(db_path, entity_type="project", name="Project Alpha")
            local_ai_id = upsert_entity(db_path, entity_type="topic", name="Local First AI")
            beta_id = upsert_entity(db_path, entity_type="project", name="Project Beta")
            add_relationship(
                db_path,
                subject_id=alpha_id,
                predicate="uses",
                object_id=local_ai_id,
                source_path="alpha.md",
                chunk_index=0,
                evidence="Project Alpha uses Local First AI.",
            )
            add_relationship(
                db_path,
                subject_id=beta_id,
                predicate="depends_on",
                object_id=alpha_id,
                source_path="beta.md",
                chunk_index=1,
                evidence="Project Beta depends on Project Alpha.",
            )

            relationships = relationships_for_entity(db_path, "Project Alpha")

        self.assertEqual(len(relationships), 2)
        self.assertEqual(
            [(item.subject_name, item.predicate, item.object_name) for item in relationships],
            [
                ("Project Alpha", "uses", "Local First AI"),
                ("Project Beta", "depends_on", "Project Alpha"),
            ],
        )

    def test_timeline_for_entity_returns_date_relationships_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "graph.sqlite"
            extract_graph_from_chunks(
                [
                    {
                        "path": "alpha-2.md",
                        "chunk_index": 1,
                        "content": "Project Alpha shipped beta on 2026-06-02.",
                    },
                    {
                        "path": "alpha-1.md",
                        "chunk_index": 0,
                        "content": "Project Alpha launched on 2026-06-01.",
                    },
                ],
                db_path=db_path,
            )

            events = timeline_for_entity(db_path, "Project Alpha")

        self.assertEqual([event.date for event in events], ["2026-06-01", "2026-06-02"])
        self.assertEqual(events[0].entity_name, "Project Alpha")
        self.assertEqual(events[0].source_path, "alpha-1.md")
        self.assertEqual(events[0].chunk_index, 0)


if __name__ == "__main__":
    unittest.main()
