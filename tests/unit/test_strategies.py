"""Incremental strategies offered by the adapter (spec 18 FR-8 to FR-12)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MACROS = ROOT / "dbt" / "include" / "iris" / "macros"


class TestValidStrategies(unittest.TestCase):
    def test_strategies(self):
        from dbt.adapters.iris.impl import IRISAdapter

        self.assertEqual(
            IRISAdapter.valid_incremental_strategies(None),
            ["append", "merge", "delete+insert", "microbatch"],
        )

    def test_insert_overwrite_is_gone(self):
        text = "\n".join(p.read_text() for p in MACROS.rglob("*.sql"))
        self.assertNotIn("insert_overwrite", text)

    def test_merge_no_longer_uses_insert_or_update(self):
        text = "\n".join(p.read_text() for p in MACROS.rglob("*.sql")).lower()
        self.assertNotIn("insert or update", text)

    def test_hash_needs_no_embedded_python(self):
        text = (MACROS / "adapters.sql").read_text()
        start = text.index("macro create_function_hash")
        body = text[start : text.index("endmacro", start)]
        self.assertNotIn("LANGUAGE PYTHON", body.upper())
        self.assertIn("LANGUAGE OBJECTSCRIPT", body.upper())


if __name__ == "__main__":
    unittest.main()
