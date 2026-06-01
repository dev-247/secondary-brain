from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.graph import (
    add_relationship,
    get_entity,
    init_graph_db,
    list_relationships,
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


if __name__ == "__main__":
    unittest.main()
