"""The merge strategy on a target with no primary key or unique index (spec 18 FR-8, US-2).

1.9.x ran merge as INSERT OR UPDATE, which matches on the target's primary key or unique index.
A table dbt builds with CREATE TABLE AS has neither, so updated rows came back as duplicates.
"""
import pytest

from dbt.tests.adapter.incremental.test_incremental_predicates import BaseIncrementalPredicates
from dbt.tests.util import run_dbt

_single = """
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='id') }}
{% if var('round', 1) == 1 %}
select 1 as id, 'a' as v, 10 as n union all select 2, 'b', 20
{% else %}
select 2 as id, 'B' as v, 21 as n union all select 3, 'c', 30
{% endif %}
"""

_composite = """
{{ config(materialized='incremental', incremental_strategy='merge', unique_key=['k1', 'k2']) }}
{% if var('round', 1) == 1 %}
select 1 as k1, 'x' as k2, 'a' as v union all select 1, 'y', 'b'
{% else %}
select 1 as k1, 'y' as k2, 'B' as v union all select 2, 'x', 'c'
{% endif %}
"""

_update_columns = """
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='id',
          merge_update_columns=['v']) }}
{% if var('round', 1) == 1 %}
select 1 as id, 'a' as v, 10 as n union all select 2, 'b', 20
{% else %}
select 2 as id, 'B' as v, 21 as n
{% endif %}
"""

_null_key = """
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='id') }}
{% if var('round', 1) == 1 %}
select cast(null as integer) as id, 'a' as v union all select 1, 'b'
{% else %}
select cast(null as integer) as id, 'A' as v
{% endif %}
"""


class TestMergeOnUnindexedTarget:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "merge_single.sql": _single,
            "merge_composite.sql": _composite,
            "merge_update_columns.sql": _update_columns,
            "merge_null_key.sql": _null_key,
        }

    def _rows(self, project, name, order):
        return project.run_sql(
            f"select * from {project.test_schema}.{name} order by {order}", fetch="all"
        )

    def test_merge(self, project):
        run_dbt(["run"])
        run_dbt(["run", "--vars", "round: 2"])
        run_dbt(["run", "--vars", "round: 2"])  # idempotent

        assert [tuple(r) for r in self._rows(project, "merge_single", "id")] == [
            (1, "a", 10),
            (2, "B", 21),
            (3, "c", 30),
        ]
        assert [tuple(r) for r in self._rows(project, "merge_composite", "k1, k2")] == [
            (1, "x", "a"),
            (1, "y", "B"),
            (2, "x", "c"),
        ]
        # only v is updated; n keeps its first value
        assert [tuple(r) for r in self._rows(project, "merge_update_columns", "id")] == [
            (1, "a", 10),
            (2, "B", 20),
        ]
        # NULL keys match each other, as in dbt's default merge (the equals() macro)
        assert [tuple(r) for r in self._rows(project, "merge_null_key", "v")] == [
            (None, "A"),
            (1, "b"),
        ]


class TestIncrementalPredicatesMerge(BaseIncrementalPredicates):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "models": {
                "+incremental_predicates": ["dbt_internal_dest.id != 2"],
                "+incremental_strategy": "merge",
            }
        }


_di_single = _single.replace(
    "incremental_strategy='merge'", "incremental_strategy='delete+insert'"
)
_di_composite = _composite.replace(
    "incremental_strategy='merge'", "incremental_strategy='delete+insert'"
)
_di_null_key = _null_key.replace(
    "incremental_strategy='merge'", "incremental_strategy='delete+insert'"
)


class TestDeleteInsertOnIntegerKeys:
    """1.9.x deleted with IFNULL(key, '') IN (...), which matches nothing for integer keys on IRIS,
    so every run added duplicates. dbt's standard unique-key suite uses string keys."""

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "di_single.sql": _di_single,
            "di_composite.sql": _di_composite,
            "di_null_key.sql": _di_null_key,
        }

    def test_delete_insert(self, project):
        run_dbt(["run"])
        run_dbt(["run", "--vars", "round: 2"])
        run_dbt(["run", "--vars", "round: 2"])
        rows = lambda name, order: [  # noqa: E731
            tuple(r)
            for r in project.run_sql(
                f"select * from {project.test_schema}.{name} order by {order}", fetch="all"
            )
        ]
        assert rows("di_single", "id") == [(1, "a", 10), (2, "B", 21), (3, "c", 30)]
        assert rows("di_composite", "k1, k2") == [(1, "x", "a"), (1, "y", "B"), (2, "x", "c")]
        assert rows("di_null_key", "v") == [(None, "A"), (1, "b")]
