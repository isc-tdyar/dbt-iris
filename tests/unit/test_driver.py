"""dbt-iris 2.0.0 connects only through intersystems-irispython (`iris.dbapi`).

The bundled 3.x driver and the `driver` choice were removed in 2.0.0. `driver: iris` is still
accepted so existing profiles keep working; any other value, in the profile or in
DBT_IRIS_DRIVER, is refused with a message naming the release that removed it.
"""
import enum
import os
import sys
import types
import unittest
from unittest import mock

from dbt.adapters.exceptions import FailedToConnectError

from dbt.adapters.iris.connections import IRISConnectionManager


class _Creds:
    def __init__(self, driver=None):
        self.hostname, self.port, self.database = "h", 1972, "USER"
        self.username, self.password = "u", "p"
        self.application_name = "dbt"
        self.driver = driver


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


def _open(driver=None, env=None):
    mods, calls = _fake_iris()
    conn = types.SimpleNamespace(state="init", credentials=_Creds(driver), handle=None)
    environ = {k: v for k, v in os.environ.items() if k != "DBT_IRIS_DRIVER"}
    if env is not None:
        environ["DBT_IRIS_DRIVER"] = env
    with mock.patch.dict(sys.modules, mods), mock.patch.dict(os.environ, environ, clear=True):
        IRISConnectionManager.open(conn)
    return conn, calls


class TestConnectsThroughIrisDbapi(unittest.TestCase):
    def test_default_profile_uses_iris_dbapi(self):
        conn, calls = _open()
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

    def test_driver_iris_is_still_accepted(self):
        conn, calls = _open(driver="iris")
        self.assertEqual(conn.handle, "HANDLE")

    def test_env_iris_is_still_accepted(self):
        conn, calls = _open(env="iris")
        self.assertEqual(conn.handle, "HANDLE")


class TestRemovedDriversAreRefused(unittest.TestCase):
    def _assert_refused(self, **kw):
        with self.assertRaises(FailedToConnectError) as ctx:
            _open(**kw)
        self.assertIn("removed in dbt-iris 2.0.0", str(ctx.exception))
        self.assertIn("intersystems-irispython", str(ctx.exception))

    def test_profile_vendored(self):
        self._assert_refused(driver="vendored")

    def test_profile_sqlalchemy(self):
        self._assert_refused(driver="sqlalchemy")

    def test_env_vendored(self):
        self._assert_refused(env="vendored")

    def test_unknown_value(self):
        self._assert_refused(driver="oracle")


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
