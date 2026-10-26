"""After the adapter adds a column to a table, a query another connection had already run on that
table still works. On IRIS 2026.3 and later, for a user with %All, the same statement text on a new
connection otherwise fails with "Invalid number of parameters" from a stale cached query. The
adapter purges the table's cached queries after its ALTER TABLE. (Snapshots that gain a column are
covered by TestSnapshotNewColumnWithDeletes.)
"""
import pytest

from dbt.tests.util import run_dbt, write_file

_v1 = """
{{ config(materialized='incremental', on_schema_change='append_new_columns') }}
select 1 as id
"""
_v2 = """
{{ config(materialized='incremental', on_schema_change='append_new_columns') }}
select 2 as id, 'b' as extra
"""


class TestCountAfterAppendNewColumns:
    @pytest.fixture(scope="class")
    def models(self):
        return {"grows.sql": _v1}

    def test_same_count_text_works_after_the_column_is_added(self, project):
        count = f"select count(*) as row_count from {project.test_schema}.grows"
        run_dbt(["run"])
        assert project.run_sql(count, fetch="one")[0] == 1

        write_file(_v2, project.project_root, "models", "grows.sql")
        run_dbt(["run"])
        assert project.run_sql(count, fetch="one")[0] == 2
