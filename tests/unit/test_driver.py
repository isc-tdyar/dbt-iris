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


class TestClassLockRetry(unittest.TestCase):
    def test_lock_errors_are_retryable(self):
        from dbt.adapters.iris.connections import _is_class_lock_conflict

        self.assertTrue(_is_class_lock_conflict(Exception("ERROR #5864: ... open for editing.")))
        self.assertTrue(
            _is_class_lock_conflict(Exception("ERROR #5803: Failed to acquire exclusive lock"))
        )

    def test_missing_class_is_retryable_only_for_ddl(self):
        from dbt.adapters.iris.connections import _is_class_lock_conflict

        missing = Exception("ERROR #5351: Class 'x.y' does not exist.")
        self.assertTrue(
            _is_class_lock_conflict(missing, "/* dbt */ create or replace view x as select 1")
        )
        self.assertTrue(_is_class_lock_conflict(missing, "drop table x"))
        self.assertFalse(_is_class_lock_conflict(missing, "select * from x"))
        self.assertFalse(
            _is_class_lock_conflict(Exception("SQLCODE -30 table not found"), "drop table x")
        )

    def test_cached_query_lock_timeout_during_prepare_is_retryable_for_any_statement(self):
        # IRIS's adaptive mode tunes a table on first use and a background worker regenerates
        # the stale cached queries holding their metadata lock; a Prepare meanwhile times out.
        # The statement never ran, so it is safe to send again (measured on 2026.1 to 2026.3).
        from dbt.adapters.iris.connections import _is_class_lock_conflict

        timeout = Exception(
            "<SQL ERROR>; Details: [SQLCODE: <-114>:<One or more matching rows is locked by "
            "another user>] [Location: <Prepare>] [%msg: <Lock Timeout attempting to acquire "
            "shared lock on Cached Query metadata during Prepare()>]"
        )
        self.assertTrue(_is_class_lock_conflict(timeout, "select count(*) from x"))
        self.assertTrue(_is_class_lock_conflict(timeout, "insert into x select * from y"))

    def test_a_row_lock_while_executing_is_not_retried(self):
        from dbt.adapters.iris.connections import _is_class_lock_conflict

        row_lock = Exception(
            "[SQLCODE: <-114>:<One or more matching rows is locked by another user>] "
            "[Location: <ServerLoop - Query Fetch>]"
        )
        self.assertFalse(_is_class_lock_conflict(row_lock, "update x set a = 1"))
