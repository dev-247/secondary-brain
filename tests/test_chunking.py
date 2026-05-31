from __future__ import annotations

import unittest

from scripts.chunking import MAX_CHUNK_CHARS, chunk_markdown, chunk_plain_text


class ChunkingTests(unittest.TestCase):
    def test_markdown_chunks_keep_headings(self) -> None:
        chunks = chunk_markdown("# Alpha\n\nFirst note.\n\n## Beta\n\nSecond note.")

        self.assertEqual([chunk.heading for chunk in chunks], ["Alpha", "Beta"])
        self.assertIn("# Alpha", chunks[0].text)
        self.assertIn("## Beta", chunks[1].text)

    def test_plain_text_splits_large_documents(self) -> None:
        text = ("Paragraph one.\n\n" * 200).strip()

        chunks = chunk_plain_text(text, title="Large")

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.heading == "Large" for chunk in chunks))
        self.assertTrue(all(len(chunk.text) <= MAX_CHUNK_CHARS for chunk in chunks))

    def test_empty_plain_text_returns_no_chunks(self) -> None:
        self.assertEqual(chunk_plain_text("   \n\n", title="Empty"), [])


if __name__ == "__main__":
    unittest.main()
