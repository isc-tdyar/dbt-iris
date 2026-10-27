"""Recursive CTE models (spec 18 FR-15, FR-16, US-4).

On a server that accepts WITH RECURSIVE the models build; on one that does not, they fail before
execution with a message naming the capability.
"""
import pytest

from dbt.tests.util import run_dbt

_edges = "parent,child\n1,2\n2,3\n3,4\n2,5\n"
_table = """
{{ config(materialized='table') }}
WITH RECURSIVE tree(node, depth) AS (
  SELECT child, 1 FROM {{ ref('edges') }} WHERE parent = 1
  UNION ALL
  SELECT e.child, t.depth + 1 FROM {{ ref('edges') }} e JOIN tree t ON e.parent = t.node
)
SELECT node, depth FROM tree
"""
_ephemeral = """
{{ config(materialized='ephemeral') }}
WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 10) SELECT n FROM r
"""
_uses_ephemeral = (
    "{{ config(materialized='table') }} select n from {{ ref('counter') }} where n > 5"
)
_view = """
{{ config(materialized='view') }}
WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 3) SELECT n FROM r
"""


def _server_accepts_recursive(project):
    try:
        project.run_sql(
            "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 2) SELECT n FROM r",
            fetch="all",
        )
        return True
    except Exception:  # noqa: BLE001
        return False


class TestRecursiveModels:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"edges.csv": _edges}

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "tree.sql": _table,
            "counter.sql": _ephemeral,
            "uses_counter.sql": _uses_ephemeral,
            "small.sql": _view,
        }

    def test_recursive_models(self, project):
        run_dbt(["seed"])
        if _server_accepts_recursive(project):
            run_dbt(["run"])
            rows = project.run_sql(
                f"select count(*), max(depth) from {project.test_schema}.tree", fetch="one"
            )
            assert tuple(rows) == (4, 3)
            (count,) = project.run_sql(
                f"select count(*) from {project.test_schema}.uses_counter", fetch="one"
            )
            assert count == 5
            (count,) = project.run_sql(
                f"select count(*) from {project.test_schema}.small", fetch="one"
            )
            assert count == 3
        else:
            results = run_dbt(["run"], expect_pass=False)
            failed = [r for r in results.results if r.status == "error"]
            assert len(failed) == 3
            for r in failed:
                assert "WITH RECURSIVE" in r.message
                assert "SQLCODE" not in r.message


# The workaround documented under "Recursive CTEs" in docs/dbt-docs-site/iris-configs.md: when the
# maximum depth is known, unroll the hierarchy into one join per level. Runs on any IRIS.
_fixed_depth = """
{{ config(materialized='table') }}
{% set max_depth = 3 %}
{% for depth in range(1, max_depth + 1) %}
select e{{ depth }}.child as node, {{ depth }} as depth
from {{ ref('edges') }} e1
{% for level in range(2, depth + 1) %}
join {{ ref('edges') }} e{{ level }} on e{{ level }}.parent = e{{ level - 1 }}.child
{% endfor %}
where e1.parent = 1
{% if not loop.last %}union all{% endif %}
{% endfor %}
"""


class TestFixedDepthWorkaround:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"edges.csv": _edges}

    @pytest.fixture(scope="class")
    def models(self):
        return {"tree_fixed_depth.sql": _fixed_depth}

    def test_same_answer_as_the_recursive_model(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        rows = project.run_sql(
            f"select node, depth from {project.test_schema}.tree_fixed_depth order by depth, node",
            fetch="all",
        )
        assert [tuple(r) for r in rows] == [(2, 1), (3, 2), (5, 2), (4, 3)]
