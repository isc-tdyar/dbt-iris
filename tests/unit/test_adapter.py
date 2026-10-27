import unittest
from multiprocessing import get_context
from unittest import mock
import dbt.flags as flags
from dbt.adapters.iris import IRISAdapter

from .utils import config_from_parts_or_dicts, mock_connection


class TestIRISAdapter(unittest.TestCase):
    def setUp(self):
        pass
        flags.STRICT_MODE = True

        profile_cfg = {
            "outputs": {
                "test": {
                    "type": "iris",
                    "hostname": "thishostshouldnotexist",
                    "port": 1972,
                    "namespace": "USER",
                    "schema": "dbt",
                    "username": "dbt",
                    "password": "dbt",
                }
            },
            "target": "test",
        }

        project_cfg = {
            "name": "X",
            "version": "0.1",
            "profile": "test",
            "project-root": "/tmp/dbt/does-not-exist",
            "quoting": {
                "identifier": False,
                "schema": True,
            },
            "config-version": 2,
        }

        self.config = config_from_parts_or_dicts(project_cfg, profile_cfg)
        self.mp_context = get_context("spawn")
        self._adapter = None

    @property
    def adapter(self):
        if self._adapter is None:
            self._adapter = IRISAdapter(self.config, self.mp_context)
        return self._adapter

    @mock.patch("dbt.adapters.iris.connections._dbapi")
    def test_acquire_connection(self, dbapi):
        connector = dbapi.return_value
        connection = self.adapter.acquire_connection("dummy")

        connector.connect.assert_not_called()
        connection.handle
        self.assertEqual(connection.state, "open")
        self.assertNotEqual(connection.handle, None)
        connector.connect.assert_called_once()

    def test_cancel_open_connections_empty(self):
        self.assertEqual(len(list(self.adapter.cancel_open_connections())), 0)

    def test_cancel_open_connections_main(self):
        key = self.adapter.connections.get_thread_identifier()
        self.adapter.connections.thread_connections[key] = mock_connection("main")
        self.assertEqual(len(list(self.adapter.cancel_open_connections())), 0)


class TestPurgeCachedQueries(unittest.TestCase):
    """purge_cached_queries runs PURGE CACHED QUERIES BY TABLE on a second connection: IRIS 2026.3
    ignores the purge when it comes from the connection that ran the ALTER. It never fails a run,
    and it is skipped on releases before 2026.3, which do not have the stale-query defect."""

    setUp = TestIRISAdapter.setUp
    adapter = TestIRISAdapter.adapter

    def _relation(self):
        relation = mock.Mock()
        relation.__str__ = mock.Mock(return_value='"dbt"."orders"')
        return relation

    def _purge(self, dbapi, version="2026.3.0L (Build 196U)"):
        self.adapter.acquire_connection("dummy").handle
        second = mock.Mock()
        dbapi.return_value.connect.side_effect = [second]
        with mock.patch("dbt.adapters.iris.capabilities.server_version", return_value=version):
            self.adapter.purge_cached_queries(self._relation())
        return second

    @mock.patch("dbt.adapters.iris.connections._dbapi")
    def test_purges_the_table_on_a_new_connection_and_closes_it(self, dbapi):
        thread_handle = dbapi.return_value.connect.return_value
        second = self._purge(dbapi)
        kwargs = dbapi.return_value.connect.call_args.kwargs
        self.assertEqual(kwargs["hostname"], "thishostshouldnotexist")
        self.assertEqual(kwargs["namespace"], "USER")
        second.cursor.return_value.execute.assert_called_once_with(
            'purge cached queries by table "dbt"."orders"'
        )
        second.close.assert_called_once()
        thread_handle.cursor.return_value.execute.assert_not_called()

    @mock.patch("dbt.adapters.iris.connections._dbapi")
    def test_releases_before_2026_3_are_skipped(self, dbapi):
        for version in ("2026.1 (Build 234U)", "2026.2 (Build 221U)", "2025.1 (Build 223U)"):
            dbapi.reset_mock()
            second = self._purge(dbapi, version)
            second.cursor.assert_not_called()

    @mock.patch("dbt.adapters.iris.connections._dbapi")
    def test_later_and_unknown_releases_are_purged(self, dbapi):
        for version in ("2026.3.0L (Build 196U)", "2027.1.0RCTE.100.0 (Build 100U)", None):
            dbapi.reset_mock()
            second = self._purge(dbapi, version)
            second.cursor.return_value.execute.assert_called_once()

    @mock.patch("dbt.adapters.iris.connections._dbapi")
    def test_a_failed_connect_is_ignored(self, dbapi):
        self.adapter.acquire_connection("dummy").handle
        dbapi.return_value.connect.side_effect = [RuntimeError("no licence")]
        with mock.patch("dbt.adapters.iris.capabilities.server_version", return_value=None):
            self.adapter.purge_cached_queries(self._relation())

    @mock.patch("dbt.adapters.iris.connections._dbapi")
    def test_a_failed_purge_is_ignored_and_the_connection_closed(self, dbapi):
        self.adapter.acquire_connection("dummy").handle
        second = mock.Mock()
        second.cursor.return_value.execute.side_effect = RuntimeError("SQLCODE: <-99>")
        dbapi.return_value.connect.side_effect = [second]
        with mock.patch("dbt.adapters.iris.capabilities.server_version", return_value=None):
            self.adapter.purge_cached_queries(self._relation())
        second.close.assert_called_once()


class TestCreateSchemaWithoutCodePrivilege(unittest.TestCase):
    """create_schema installs HASH() for snapshots. IRIS refuses CREATE FUNCTION with code to a
    user without %Developer (SQLCODE -99), which used to fail every run on a new schema; now only
    snapshots need the privilege, and the run is told so."""

    setUp = TestIRISAdapter.setUp
    adapter = TestIRISAdapter.adapter

    def test_privilege_violation_is_a_warning(self):
        from dbt_common.exceptions import DbtDatabaseError

        error = DbtDatabaseError(
            "<SQL ERROR>; Details: [SQLCODE: <-99>:<Privilege violation>] [%msg: <User dbt does "
            "not have privilege to CREATE FUNCTION with custom code>]"
        )
        with mock.patch.object(self.adapter, "execute_macro", side_effect=error), mock.patch(
            "dbt.adapters.iris.impl.logger"
        ) as logger:
            self.adapter.create_schema(mock.Mock())
        message = logger.warning.call_args.args[0]
        self.assertIn("HASH", message)
        self.assertIn("%Developer", message)
        self.assertIn("snapshot", message)
        self.assertIn("Python models", message)

    def test_other_errors_still_fail(self):
        from dbt_common.exceptions import DbtDatabaseError

        error = DbtDatabaseError("[SQLCODE: <-400>:<Fatal error occurred>]")
        with mock.patch.object(self.adapter, "execute_macro", side_effect=error):
            with self.assertRaises(DbtDatabaseError):
                self.adapter.create_schema(mock.Mock())
