"""Repeated runs leave only the models' own relations in the schema. Temporary, intermediate and
backup tables carry the invocation id, so one left behind is a new table on every run."""
import pytest

from dbt.tests.util import run_dbt

_table = "{{ config(materialized='table') }} select 1 as id"
_incremental = """
{{ config(materialized='incremental', unique_key='id') }}
select 1 as id, current_timestamp as loaded_at
"""
_incremental_merge = """
{{ config(materialized='incremental', unique_key='id', incremental_strategy='merge') }}
select 1 as id, current_timestamp as loaded_at
"""
_source = "{{ config(materialized='table') }} select 1 as id, 'a' as v"
_snapshot = """
{% snapshot snap %}
{{ config(target_schema=schema, unique_key='id', strategy='check', check_cols=['v']) }}
select * from {{ ref('source_rows') }}
{% endsnapshot %}
"""


class TestNoLeftoverTables:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "a_table.sql": _table,
            "an_incremental.sql": _incremental,
            "a_merge.sql": _incremental_merge,
            "source_rows.sql": _source,
        }

    @pytest.fixture(scope="class")
    def snapshots(self):
        return {"snap.sql": _snapshot}

    def test_three_builds_leave_only_the_models(self, project):
        for _ in range(3):
            run_dbt(["build"])
        rows = project.run_sql(
            "select table_name from information_schema.tables "
            f"where table_schema = '{project.test_schema}'",
            fetch="all",
        )
        assert sorted(r[0].lower() for r in rows) == [
            "a_merge", "a_table", "an_incremental", "snap", "source_rows"
        ]  # fmt: skip
