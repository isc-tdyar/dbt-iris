"""Driver selection: which DB-API module the adapter connects through.

Three choices, resolved in this order: the profile's `driver` field, the
DBT_IRIS_DRIVER environment variable, then auto-detect (prefer `iris.dbapi`
if importable, else the vendored `intersystems_iris` package).
"""
import os
import sys
import types
import unittest
from unittest import mock

from dbt.adapters.iris.connections import (
    DRIVER_ENV,
    resolve_driver,
    load_dbapi,
)


class _Creds:
    def __init__(self, driver=None):
        self.driver = driver


class TestResolveDriver(unittest.TestCase):
    def test_profile_field_wins(self):
        with mock.patch.dict(os.environ, {DRIVER_ENV: "vendored"}):
            self.assertEqual(resolve_driver(_Creds("sqlalchemy")), "sqlalchemy")

    def test_env_used_when_profile_unset(self):
        with mock.patch.dict(os.environ, {DRIVER_ENV: "vendored"}):
            self.assertEqual(resolve_driver(_Creds()), "vendored")

    def test_auto_prefers_iris_dbapi_when_importable(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(DRIVER_ENV, None)
            fake = types.ModuleType("iris.dbapi")
            with mock.patch.dict(
                sys.modules, {"iris": types.ModuleType("iris"), "iris.dbapi": fake}
            ):
                self.assertEqual(resolve_driver(_Creds()), "iris")

    def test_auto_falls_back_to_vendored(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(DRIVER_ENV, None)
            with mock.patch.dict(sys.modules, {"iris": None, "iris.dbapi": None}):
                self.assertEqual(resolve_driver(_Creds()), "vendored")

    def test_unknown_value_raises(self):
        with self.assertRaises(ValueError):
            resolve_driver(_Creds("oracle"))


class TestLoadDbapi(unittest.TestCase):
    def test_iris_loads_iris_dbapi(self):
        fake = types.ModuleType("iris.dbapi")
        with mock.patch.dict(sys.modules, {"iris": types.ModuleType("iris"), "iris.dbapi": fake}):
            self.assertIs(load_dbapi("iris"), fake)

    def test_vendored_loads_intersystems_iris(self):
        fake = types.ModuleType("intersystems_iris.dbapi._DBAPI")
        mods = {
            "intersystems_iris": types.ModuleType("intersystems_iris"),
            "intersystems_iris.dbapi": types.ModuleType("intersystems_iris.dbapi"),
            "intersystems_iris.dbapi._DBAPI": fake,
        }
        with mock.patch.dict(sys.modules, mods):
            self.assertIs(load_dbapi("vendored"), fake)

    def test_sqlalchemy_returns_none_module(self):
        """SQLAlchemy path builds an engine in open(); no DB-API module to load."""
        self.assertIsNone(load_dbapi("sqlalchemy"))


class _LiveRow:
    """Mimics irispython 5.x DataRow: a proxy that dies when its cursor closes."""

    def __init__(self, cursor, values):
        self._cursor, self._values = cursor, values

    def __iter__(self):
        if self._cursor.closed:
            raise RuntimeError("Cursor closed; DataRow is inaccessible")
        return iter(self._values)

    def __getitem__(self, i):
        if self._cursor.closed:
            raise RuntimeError("Cursor closed; DataRow is inaccessible")
        return self._values[i]


class _Cursor:
    def __init__(self, rows):
        self.closed = False
        self.description = [("id",), ("name",)]
        self._rows = [_LiveRow(self, r) for r in rows]

    def fetchall(self):
        return self._rows

    def fetchmany(self, n):
        return self._rows[:n]

    def close(self):
        self.closed = True


class TestResultsDetachFromCursor(unittest.TestCase):
    """dbt reads result rows after the adapter has closed the cursor. With the
    compiled driver, rows are live proxies, so they must be copied out first."""

    def test_rows_survive_cursor_close(self):
        from dbt.adapters.iris.connections import IRISConnectionManager

        cur = _Cursor([(1, "a"), (2, "b")])
        table = IRISConnectionManager.get_result_from_cursor(cur, None)
        cur.close()
        self.assertEqual([tuple(r) for r in table.rows], [(1, "a"), (2, "b")])

    def test_limit_uses_fetchmany(self):
        from dbt.adapters.iris.connections import IRISConnectionManager

        cur = _Cursor([(1, "a"), (2, "b"), (3, "c")])
        table = IRISConnectionManager.get_result_from_cursor(cur, 2)
        cur.close()
        self.assertEqual(len(table.rows), 2)
