"""dbt's snapshot suites beyond the basic two: column names, dbt_valid_to_current, multi-column
unique keys, hard_deletes modes, and new columns (dbt 1.9 snapshot configuration).

The suites run as upstream wrote them. Where their setup or expected-state SQL is Postgres
(three-part names, multi-row VALUES, ``::`` casts, md5, interval arithmetic, a boolean in a select
list), the fixture or method is replaced by its IRIS translation from snapshot_fixtures_iris; the
rows and the assertions are unchanged.
"""
import pytest

from dbt.tests.adapter.simple_snapshot.new_record_check_mode import BaseSnapshotNewRecordCheckMode
from dbt.tests.adapter.simple_snapshot.new_record_dbt_valid_to_current import (
    BaseSnapshotNewRecordDbtValidToCurrent,
)
from dbt.tests.adapter.simple_snapshot.new_record_timestamp_mode import (
    BaseSnapshotNewRecordTimestampMode,
)
from dbt.tests.adapter.simple_snapshot.test_ephemeral_snapshot_hard_deletes import (
    BaseSnapshotEphemeralHardDeletes,
    BaseSnapshotNewColumnSpecificCheckCols,
    BaseSnapshotNewColumnTimestampStrategy,
    BaseSnapshotNewColumnWithDeletes,
)
from dbt.tests.adapter.simple_snapshot.test_snapshot import BaseSimpleSnapshot, BaseSnapshotCheck
from dbt.tests.adapter.simple_snapshot.test_various_configs import (
    BaseSnapshotColumnNames,
    BaseSnapshotColumnNamesFromDbtProject,
    BaseSnapshotDbtValidToCurrent,
    BaseSnapshotInvalidColumnNames,
    BaseSnapshotMultiUniqueKey,
)
from dbt.tests.adapter.simple_snapshot import fixtures as upstream_fixtures
from dbt.tests.adapter.simple_snapshot import test_various_configs
from dbt.tests.util import run_dbt

from tests.functional.adapter import snapshot_fixtures_iris as iris_fixtures

# test_snapshot.py


class IrisSnapshotResults:
    def _assert_results(
        self,
        ids_with_current_snapshot_records,
        ids_with_closed_out_snapshot_records,
    ):
        # Upstream selects "dbt_valid_to is null as is_current"; IRIS has no boolean expression
        # in a select list, so the flag comes back as 1 or 0.
        records = {
            (id_, bool(is_current))
            for id_, is_current in self.get_snapshot_records(
                "id, case when dbt_valid_to is null then 1 else 0 end as is_current"
            )
        }
        expected_records = set().union(
            {(i, True) for i in ids_with_current_snapshot_records},
            {(i, False) for i in ids_with_closed_out_snapshot_records},
        )
        for record in records:
            assert record in expected_records


# The seed's updated_at is a DATE; IRIS's DATEADD returns a TIMESTAMP, so cast it back.
_PLUS_ONE_DAY = "cast(dateadd('day', 1, updated_at) as date)"


class TestSimpleSnapshot(IrisSnapshotResults, BaseSimpleSnapshot):
    def test_updates_are_captured_by_snapshot(self, project):
        self.update_fact_records({"updated_at": _PLUS_ONE_DAY}, "id between 16 and 20")
        run_dbt(["snapshot"])
        self._assert_results(
            ids_with_current_snapshot_records=range(1, 21),
            ids_with_closed_out_snapshot_records=range(16, 21),
        )

    def test_new_column_captured_by_snapshot(self, project):
        self.add_fact_column("full_name", "varchar(200) default null")
        self.update_fact_records(
            {
                "full_name": "first_name || ' ' || last_name",
                "updated_at": _PLUS_ONE_DAY,
            },
            "id between 11 and 20",
        )
        run_dbt(["snapshot"])
        self._assert_results(
            ids_with_current_snapshot_records=range(1, 21),
            ids_with_closed_out_snapshot_records=range(11, 21),
        )


class TestSnapshotCheck(IrisSnapshotResults, BaseSnapshotCheck):
    pass


# test_various_configs.py: the test methods read the fixture SQL from module globals, so the
# IRIS translations replace those globals for the duration of each test.

_VARIOUS_CONFIGS_SQL = [
    "create_seed_sql",
    "create_snapshot_expected_sql",
    "seed_insert_sql",
    "populate_snapshot_expected_sql",
    "populate_snapshot_expected_valid_to_current_sql",
    "invalidate_sql",
    "update_sql",
    "update_with_current_sql",
    "create_multi_key_seed_sql",
    "create_multi_key_snapshot_expected_sql",
    "seed_multi_key_insert_sql",
    "populate_multi_key_snapshot_expected_sql",
    "invalidate_multi_key_sql",
    "update_multi_key_sql",
]


class IrisVariousConfigsSql:
    @pytest.fixture(autouse=True)
    def _iris_sql(self, monkeypatch):
        for name in _VARIOUS_CONFIGS_SQL:
            assert hasattr(test_various_configs, name), name
            monkeypatch.setattr(test_various_configs, name, getattr(iris_fixtures, name))


class IrisSnapshotActual(IrisVariousConfigsSql):
    @pytest.fixture(scope="class")
    def snapshots(self):
        return {"snapshot.sql": iris_fixtures.snapshot_actual_sql}


class TestSnapshotColumnNames(IrisSnapshotActual, BaseSnapshotColumnNames):
    pass


class TestSnapshotColumnNamesFromDbtProject(
    IrisSnapshotActual, BaseSnapshotColumnNamesFromDbtProject
):
    pass


class TestSnapshotInvalidColumnNames(IrisSnapshotActual, BaseSnapshotInvalidColumnNames):
    pass


class TestSnapshotDbtValidToCurrent(IrisSnapshotActual, BaseSnapshotDbtValidToCurrent):
    pass


class TestSnapshotMultiUniqueKey(IrisVariousConfigsSql, BaseSnapshotMultiUniqueKey):
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "seed.sql": iris_fixtures.model_seed_sql,
            "snapshots.yml": upstream_fixtures.snapshots_multi_key_yml,
            "ref_snapshot.sql": upstream_fixtures.ref_snapshot_sql,
        }


# new_record_*.py


class IrisNewRecordSql:
    @pytest.fixture(scope="class")
    def snapshots(self):
        return {"snapshot.sql": iris_fixtures.new_record_snapshot_actual_sql}

    @pytest.fixture(scope="class")
    def seed_new_record_mode_statements(self):
        return iris_fixtures.seed_new_record_mode_statements

    @pytest.fixture(scope="class")
    def invalidate_sql_statements(self):
        return iris_fixtures.new_record_invalidate_sql_statements

    @pytest.fixture(scope="class")
    def update_sql(self):
        return iris_fixtures.new_record_update_sql

    @pytest.fixture(scope="class")
    def delete_sql(self):
        return iris_fixtures.new_record_delete_sql

    @pytest.fixture(scope="class")
    def reinsert_sql(self):
        return iris_fixtures.new_record_reinsert_sql


class TestSnapshotNewRecordTimestampMode(IrisNewRecordSql, BaseSnapshotNewRecordTimestampMode):
    pass


class TestSnapshotNewRecordCheckMode(IrisNewRecordSql, BaseSnapshotNewRecordCheckMode):
    pass


class TestSnapshotNewRecordDbtValidToCurrent(BaseSnapshotNewRecordDbtValidToCurrent):
    @pytest.fixture(scope="class")
    def snapshots(self):
        return {"snapshot.sql": iris_fixtures.valid_to_current_snapshot_actual_sql}

    @pytest.fixture(scope="class")
    def seed_new_record_mode_statements(self):
        return iris_fixtures.valid_to_current_seed_statements

    @pytest.fixture(scope="class")
    def delete_sql(self):
        return iris_fixtures.valid_to_current_delete_sql


# test_ephemeral_snapshot_hard_deletes.py


class IrisSourceSql:
    @pytest.fixture(scope="class")
    def source_create_sql(self):
        return iris_fixtures.source_create_sql

    @pytest.fixture(scope="class")
    def source_insert_sql(self):
        return iris_fixtures.source_insert_sql

    @pytest.fixture(scope="class")
    def source_alter_sql(self):
        return iris_fixtures.source_alter_sql

    @pytest.fixture(scope="class")
    def source_delete_sql(self):
        return iris_fixtures.source_delete_sql


class TestSnapshotEphemeralHardDeletes(IrisSourceSql, BaseSnapshotEphemeralHardDeletes):
    pass


class TestSnapshotNewColumnTimestampStrategy(
    IrisSourceSql, BaseSnapshotNewColumnTimestampStrategy
):
    pass


class TestSnapshotNewColumnSpecificCheckCols(
    IrisSourceSql, BaseSnapshotNewColumnSpecificCheckCols
):
    pass


# On 2026.3.0L.196 and 2027.1.0RCTE.100 (not 2026.2): after another connection runs
# ALTER TABLE ... ADD COLUMN, a new connection running the same count(*) text fails with "Invalid
# number of parameters" (irispython-dx dxlab/stale_count_probe3.py). Not strict: passes on 2026.2.
class TestSnapshotNewColumnWithDeletes(IrisSourceSql, BaseSnapshotNewColumnWithDeletes):
    @pytest.mark.xfail(
        strict=False,
        reason="IRIS 2026.3 cached-query regression after ALTER TABLE ADD COLUMN from another connection",
    )
    def test_snapshot_new_column_with_deletes(
        self, project, source_create_sql, source_insert_sql, source_alter_sql, source_delete_sql
    ):
        super().test_snapshot_new_column_with_deletes(
            project, source_create_sql, source_insert_sql, source_alter_sql, source_delete_sql
        )
