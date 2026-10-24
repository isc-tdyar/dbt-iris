"""View materialization builds real views, also under dependent views (spec 18 FR-18, issue #5)."""
import pytest

from dbt.tests.util import run_dbt

_base = "{{ config(materialized='table') }} select 1 as id, 'a' as v"
_v1 = "{{ config(materialized='view') }} select id, v from {{ ref('base') }}"
_v2 = "{{ config(materialized='view') }} select id from {{ ref('v1') }}"


class TestViewsAreViews:
    @pytest.fixture(scope="class")
    def models(self):
        return {"base.sql": _base, "v1.sql": _v1, "v2.sql": _v2}

    def _type(self, project, name):
        (kind,) = project.run_sql(
            "select table_type from information_schema.tables "
            f"where table_schema = '{project.test_schema}' and table_name = '{name}'",
            fetch="one",
        )
        return kind

    def test_views_survive_rebuilds(self, project):
        for _ in range(3):  # each rebuild replaces base and v1 while v2 depends on them
            results = run_dbt(["run"])
            assert len(results) == 3
        assert self._type(project, "v1") == "VIEW"
        assert self._type(project, "v2") == "VIEW"
        assert self._type(project, "base") == "BASE TABLE"
        assert project.run_sql(f"select id from {project.test_schema}.v2", fetch="all") == [(1,)]
