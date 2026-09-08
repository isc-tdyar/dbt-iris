"""The adapter connects only through intersystems-irispython (`iris.dbapi`)."""
import enum
import sys
import types
import unittest
from unittest import mock

from dbt.adapters.iris.connections import IRISConnectionManager


class _Creds:
    def __init__(self):
        self.hostname, self.port, self.database = "h", 1972, "USER"
        self.username, self.password = "u", "p"
        self.application_name = "dbt"


def _fake_iris():
    calls = []

    class SQLType(enum.IntEnum):
        VARCHAR = 12
        INTEGER = 4

    dbapi = types.ModuleType("iris.dbapi")
    dbapi.connect = lambda **kw: calls.append(kw) or "HANDLE"
    dbapi.SQLType = SQLType
    pkg = types.ModuleType("iris")
    pkg.dbapi = dbapi
    return {"iris": pkg, "iris.dbapi": dbapi}, calls


class TestConnectsThroughIrisDbapi(unittest.TestCase):
    def test_open_connects_through_iris_dbapi(self):
        mods, calls = _fake_iris()
        conn = types.SimpleNamespace(state="init", credentials=_Creds(), handle=None)
        with mock.patch.dict(sys.modules, mods):
            IRISConnectionManager.open(conn)
        self.assertEqual(conn.handle, "HANDLE")
        self.assertEqual(conn.state, "open")
        self.assertEqual(
            calls,
            [
                {
                    "hostname": "h",
                    "port": 1972,
                    "namespace": "USER",
                    "username": "u",
                    "password": "p",
                }
            ],
        )


class TestTypeNames(unittest.TestCase):
    def test_type_code_names_come_from_iris_dbapi(self):
        mods, _ = _fake_iris()
        with mock.patch.dict(sys.modules, mods):
            self.assertEqual(IRISConnectionManager.data_type_code_to_name(12), "VARCHAR")

    def test_no_reference_to_the_bundled_driver_remains(self):
        import dbt.adapters.iris.connections as c

        source = open(c.__file__).read()
        self.assertNotIn("intersystems_iris", source)
        self.assertNotIn("sqlalchemy", source)


if __name__ == "__main__":
    unittest.main()
