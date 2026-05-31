from __future__ import annotations

import unittest

from scripts.router import choose_mode


class RouterTests(unittest.TestCase):
    def test_short_query_uses_fast_mode(self) -> None:
        self.assertEqual(choose_mode("What is this note about?"), "fast")

    def test_analytical_query_uses_deep_mode(self) -> None:
        query = "Compare these notes and explain in detail what contradictions exist."

        self.assertEqual(choose_mode(query), "deep")

    def test_force_deep_overrides_query_shape(self) -> None:
        self.assertEqual(choose_mode("Short?", force_deep=True), "deep")


if __name__ == "__main__":
    unittest.main()
