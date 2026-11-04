"""Python models reach IRIS through the dialect the environment has.

With the irispython-dx layer, iris+dx:/// (in-process inside IRIS, or the profile's connection
when the model runs in the dbt process); without it, the official dialect over the profile's
connection in the dbt process, and inside IRIS sqlalchemy-iris's iris+emb dialect, as in 2.0.0.
None of them needs the 3.x intersystems_iris package."""
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

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
        scope = {"_iris_engine": lambda: "ENGINE", "pandas": fake_pandas, "DataFrame": dict}
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


class TestTheEngineTheModelGets(unittest.TestCase):
    def setUp(self):
        macro = (
            ROOT / "dbt" / "include" / "iris" / "macros" / "materializations" / "table.sql"
        ).read_text()
        self.source = macro[macro.index("def _iris_engine():") : macro.index("class DataFrame(")]

    def _engine(self, modules, creator=None):
        made = []
        scope = {"create_engine": lambda url, **kw: made.append((url, sorted(kw))) or url}
        if creator is not None:
            scope["DBT_IRIS_CONNECT"] = creator
        exec(self.source, scope)
        with mock.patch.dict(sys.modules, modules):
            for name in ("iris_dx", "sqlalchemy_iris"):
                if name not in modules:
                    sys.modules.pop(name, None)
            with mock.patch("builtins.__import__", _only(modules)):
                scope["_iris_engine"]()
        return made

    def test_inside_iris_with_the_layer_it_is_in_process(self):
        made = self._engine({"iris_dx": types.ModuleType("iris_dx")})
        self.assertEqual(made, [("iris+dx:///", [])])

    def test_in_the_dbt_process_with_the_layer_it_is_the_profiles_connection(self):
        made = self._engine({"iris_dx": types.ModuleType("iris_dx")}, creator=lambda: None)
        self.assertEqual(made, [("iris+dx:///", ["creator"])])

    def test_in_the_dbt_process_without_the_layer_it_is_the_official_dialect(self):
        made = self._engine({}, creator=lambda: None)
        self.assertEqual(made, [("iris://", ["creator"])])

    def test_inside_iris_without_the_layer_it_is_sqlalchemy_iris_as_in_2_0_0(self):
        made = self._engine({"sqlalchemy_iris": types.ModuleType("sqlalchemy_iris")})
        self.assertEqual(made, [("iris+emb:///", [])])


def _only(available):
    """An __import__ that finds only the named optional modules."""
    real = __import__

    def fake(name, *args, **kwargs):
        if name in ("iris_dx", "sqlalchemy_iris") and name not in available:
            raise ImportError(name)
        if name in available:
            return available[name]
        return real(name, *args, **kwargs)

    return fake


if __name__ == "__main__":
    unittest.main()
