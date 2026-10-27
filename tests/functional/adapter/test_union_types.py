"""A table or incremental model whose UNION gives a column a DATE or TIME in one branch and text in
another fails before IRIS stores the wrong values ('66154' for 2022-02-14). Views, NULL branches
and branches of one type are left alone."""
import pytest

from dbt.tests.util import run_dbt, run_dbt_and_capture

_date_and_text = """
{{ config(materialized='table') }}
select 1 as id, cast('2022-02-14' as date) as visited
union all select 2, '2022-02-15'
"""
_time_and_text = """
{{ config(materialized='table') }}
select cast('10:11:12' as time) as at_time union all select '10:11:13'
"""
_in_a_cte = """
{{ config(materialized='table') }}
with both_kinds as (
    select cast('2022-02-14' as date) as visited union all select '2022-02-15'
)
select visited from both_kinds
"""
_incremental = """
{{ config(materialized='incremental') }}
select cast('2022-02-14' as date) as visited union all select '2022-02-15'
"""
_all_dates = """
{{ config(materialized='table') }}
select cast('2022-02-14' as date) as visited union all select cast('2022-02-15' as date)
"""
_date_and_null = """
{{ config(materialized='table') }}
select cast('2022-02-14' as date) as visited union all select null
"""
_view = """
{{ config(materialized='view') }}
select cast('2022-02-14' as date) as visited union all select '2022-02-15'
"""


def _relations(project):
    rows = project.run_sql(
        "select table_name from information_schema.tables "
        f"where table_schema = '{project.test_schema}'",
        fetch="all",
    )
    return {r[0].lower() for r in rows}


class TestRefused:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "date_and_text.sql": _date_and_text,
            "time_and_text.sql": _time_and_text,
            "in_a_cte.sql": _in_a_cte,
            "incremental_mix.sql": _incremental,
        }

    def test_each_fails_with_the_column_and_the_fix_and_builds_nothing(self, project):
        results, log = run_dbt_and_capture(["run"], expect_pass=False)
        by_name = {r.node.name: r for r in results}
        for name, column in (
            ("date_and_text", "visited"),
            ("time_and_text", "at_time"),
            ("in_a_cte", "visited"),
            ("incremental_mix", "visited"),
        ):
            assert by_name[name].status == "error", name
            text = by_name[name].message
            assert column in text.lower(), text
            assert "UNION branch" in text and "cast(" in text, text
        assert not _relations(project) & {
            "date_and_text", "time_and_text", "in_a_cte", "incremental_mix"
        }  # fmt: skip


class TestAllowed:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "all_dates.sql": _all_dates,
            "date_and_null.sql": _date_and_null,
            "a_view.sql": _view,
        }

    def test_same_types_null_branches_and_views_build(self, project):
        run_dbt(["run"])
        for name in ("all_dates", "date_and_null"):
            rows = project.run_sql(
                f"select visited from {project.test_schema}.{name} where visited is not null",
                fetch="all",
            )
            assert {str(r[0]) for r in rows} <= {"2022-02-14", "2022-02-15"}, (name, rows)
        rows = project.run_sql(f"select visited from {project.test_schema}.a_view", fetch="all")
        assert sorted(str(r[0]) for r in rows) == ["2022-02-14", "2022-02-15"]
