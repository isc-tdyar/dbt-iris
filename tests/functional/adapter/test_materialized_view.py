"""materialized_view on IRIS (no materialized views on any IRIS build yet): built as a table,
rebuilt on every dbt run, with a warning, so projects written for other warehouses run unchanged.
"""
import pytest

from dbt.tests.util import run_dbt, run_dbt_and_capture

_base = "{{ config(materialized='table') }} select 1 as id union all select 2"
_mv = """
{{ config(materialized='materialized_view', on_configuration_change='apply') }}
select count(*) as n from {{ ref('base') }}
"""


class TestMaterializedViewAsTable:
    @pytest.fixture(scope="class")
    def models(self):
        return {"base.sql": _base, "mv.sql": _mv}

    def _count(self, project):
        (n,) = project.run_sql(f"select n from {project.test_schema}.mv", fetch="one")
        return n

    def test_built_as_a_table_and_refreshed_each_run(self, project):
        results, log = run_dbt_and_capture(["run"])
        assert len(results) == 2
        assert "IRIS has no materialized views" in log
        assert self._count(project) == 2
        (kind,) = project.run_sql(
            "select table_type from information_schema.tables "
            f"where table_schema = '{project.test_schema}' and table_name = 'mv'",
            fetch="one",
        )
        assert kind == "BASE TABLE"

        project.run_sql(f"insert into {project.test_schema}.base (id) select 3")
        assert self._count(project) == 2  # not refreshed until dbt runs
        run_dbt(["run", "--select", "mv"])
        assert self._count(project) == 3
