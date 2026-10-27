"""A model with GROUP BY <number> fails with a message, because IRIS reads the number as a
constant and would return one group. The same model with the column named builds."""
import pytest

from dbt.tests.util import run_dbt

_rows = "select 1 as id, 'a' as s union all select 2, 'b' union all select 3, 'a'"
_by_number = (
    "{{ config(materialized='table') }} select s, count(*) as n from {{ ref('base') }} group by 1"
)
_by_name = (
    "{{ config(materialized='table') }} select s, count(*) as n from {{ ref('base') }} group by s"
)
_view_by_number = (
    "{{ config(materialized='view') }} select s, count(*) as n from {{ ref('base') }} group by 1"
)


class TestGroupByNumbers:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "base.sql": "{{ config(materialized='table') }} " + _rows,
            "by_number.sql": _by_number,
            "by_name.sql": _by_name,
            "view_by_number.sql": _view_by_number,
        }

    def test_number_refused_name_builds(self, project):
        results = run_dbt(["run"], expect_pass=False)
        status = {r.node.name: r.status for r in results}
        assert status["base"] == "success" and status["by_name"] == "success"
        for name in ("by_number", "view_by_number"):
            assert status[name] == "error", name
            message = next(r.message for r in results if r.node.name == name)
            assert "GROUP BY 1" in message and "constant" in message, message
        rows = project.run_sql(
            f"select s, n from {project.test_schema}.by_name order by s", fetch="all"
        )
        # GROUP BY returns the upper-case form under IRIS's default collation.
        assert [(r[0].lower(), r[1]) for r in rows] == [("a", 2), ("b", 1)]
