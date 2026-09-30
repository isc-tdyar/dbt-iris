"""Python models run inside IRIS through sqlalchemy-iris's iris+emb dialect, which
no longer comes with the intersystems_iris package."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestPythonModelMacro(unittest.TestCase):
    def setUp(self):
        self.macro = (
            ROOT / "dbt" / "include" / "iris" / "macros" / "materializations" / "table.sql"
        ).read_text()

    def test_checks_for_the_dialect_it_uses(self):
        self.assertIn("import sqlalchemy_iris", self.macro)
        self.assertIn("create_engine('iris+emb:///')", self.macro)

    def test_does_not_require_the_3x_driver(self):
        self.assertNotIn("import intersystems_iris", self.macro)

    def _session(self, calls):
        """The macro's IRISSession class, run with a fake engine and pandas."""
        start = self.macro.index("class IRISSession:")
        end = self.macro.index("session = IRISSession()")
        fake_pandas = type(
            "pandas",
            (),
            {
                "read_sql_table": staticmethod(
                    lambda t, e, schema: calls.append((schema, t)) or {}
                ),
            },
        )
        scope = {"create_engine": lambda url: url, "pandas": fake_pandas, "DataFrame": dict}
        exec(self.macro[start:end], scope)
        return scope["IRISSession"]()

    def test_reads_a_quoted_relation_by_its_bare_names(self):
        calls = []
        self._session(calls).table('"test_schema"."my_sql_model"')
        self.assertEqual(calls, [("test_schema", "my_sql_model")])

    def test_reads_an_unqualified_table_from_the_default_schema(self):
        calls = []
        self._session(calls).table("my_sql_model")
        self.assertEqual(calls, [("SQLUser", "my_sql_model")])


if __name__ == "__main__":
    unittest.main()
