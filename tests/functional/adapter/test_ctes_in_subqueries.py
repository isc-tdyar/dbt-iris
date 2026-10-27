"""Models with a WITH inside a subquery build as tables and as views. IRIS refuses such a WITH
(SQLCODE -1 or -12); 1.9.x's bundled driver rewrote it on the client, and the adapter now lifts it
into the statement's top-level WITH."""
import pytest

from dbt.tests.util import run_dbt

_SHAPES = {
    "derived_table": "select s.a from (with x as (select 1 as a) select a from x) s",
    "in_subquery": "select 1 as a where 1 in (with x as (select 1 as a) select a from x)",
    "union_branch": "select 0 as a union all select a from (with x as (select 1 as a) select a from x) s",
    "scalar_subquery": "select (with x as (select 1 as a) select max(a) from x) as a",
    "inside_a_cte": "with base as (select 1 as b), t as (select a from (with x as (select b as a from base) select a from x) s) select a from t",
}
_EXPECTED = {
    "derived_table": [1],
    "in_subquery": [1],
    "union_branch": [0, 1],
    "scalar_subquery": [1],
    "inside_a_cte": [1],
}


class TestCtesInSubqueries:
    @pytest.fixture(scope="class")
    def models(self):
        models = {}
        for name, sql in _SHAPES.items():
            models[f"{name}_table.sql"] = "{{ config(materialized='table') }}\n" + sql
            models[f"{name}_view.sql"] = "{{ config(materialized='view') }}\n" + sql
        return models

    def test_each_shape_builds_and_returns_its_rows(self, project):
        results = run_dbt(["run"])
        assert len(results) == 2 * len(_SHAPES)
        for name, expected in _EXPECTED.items():
            for kind in ("table", "view"):
                rows = project.run_sql(
                    f"select a from {project.test_schema}.{name}_{kind} order by a", fetch="all"
                )
                assert [r[0] for r in rows] == expected, (name, kind, rows)
