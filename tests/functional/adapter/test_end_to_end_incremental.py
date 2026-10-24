"""Spec 18 gate SC-2 (US-2, US-3): merge, delete+insert and microbatch models on unindexed
targets, plus a snapshot, over three rounds. Run in the gate on a server without Embedded Python.
"""
import pytest

from dbt.tests.util import run_dbt

try:
    from dbt.tests.util import patch_microbatch_end_time
except ImportError:  # dbt before 1.9
    from freezegun import freeze_time as patch_microbatch_end_time

_src = """
{{ config(materialized='table', event_time='event_time') }}
{% if var('round', 1) == 1 %}
select 1 as id, 'a' as v, cast('2026-10-20 10:00:00' as timestamp) as event_time,
       cast('2026-10-20 10:00:00' as timestamp) as updated_at
union all
select 2, 'b', cast('2026-10-21 10:00:00' as timestamp), cast('2026-10-20 10:00:00' as timestamp)
{% else %}
select 1 as id, 'a' as v, cast('2026-10-20 10:00:00' as timestamp) as event_time,
       cast('2026-10-20 10:00:00' as timestamp) as updated_at
union all
select 2, 'B', cast('2026-10-21 10:00:00' as timestamp), cast('2026-10-22 09:00:00' as timestamp)
union all
select 3, 'c', cast('2026-10-22 10:00:00' as timestamp), cast('2026-10-22 09:00:00' as timestamp)
{% endif %}
"""

_merge = "{{ config(materialized='incremental', incremental_strategy='merge', unique_key='id') }} select id, v from {{ ref('src') }}"
_delete_insert = "{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='id') }} select id, v from {{ ref('src') }}"
_microbatch = """
{{ config(materialized='incremental', incremental_strategy='microbatch', unique_key='id', event_time='event_time',
          batch_size='day', begin=modules.datetime.datetime(2026, 10, 20, 0, 0, 0)) }}
select id, v, event_time from {{ ref('src') }}
"""
_snapshot = """
{% snapshot snap %}
{{ config(target_schema=schema, unique_key='id', strategy='timestamp', updated_at='updated_at') }}
select id, v, updated_at from {{ ref('src') }}
{% endsnapshot %}
"""


class TestEndToEndIncrementalAndSnapshot:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "src.sql": _src,
            "inc_merge.sql": _merge,
            "inc_delete_insert.sql": _delete_insert,
            "inc_microbatch.sql": _microbatch,
        }

    @pytest.fixture(scope="class")
    def snapshots(self):
        return {"snap.sql": _snapshot}

    def _rows(self, project, name, cols="id, v"):
        return [
            tuple(r)
            for r in project.run_sql(
                f"select {cols} from {project.test_schema}.{name} order by id", fetch="all"
            )
        ]

    def _round(self, n):
        args = [] if n == 1 else ["--vars", "round: 2"]
        with patch_microbatch_end_time("2026-10-23 12:00:00"):
            run_dbt(["run"] + args)
        run_dbt(["snapshot"] + args)

    def test_three_rounds(self, project):
        self._round(1)
        assert self._rows(project, "inc_merge") == [(1, "a"), (2, "b")]
        assert self._rows(project, "inc_delete_insert") == [(1, "a"), (2, "b")]
        assert [r[0] for r in self._rows(project, "inc_microbatch", "id")] == [1, 2]
        assert len(self._rows(project, "snap", "id")) == 2

        for _ in (2, 3):  # round 3 repeats round 2 and must change nothing
            self._round(2)
            assert self._rows(project, "inc_merge") == [(1, "a"), (2, "B"), (3, "c")]
            assert self._rows(project, "inc_delete_insert") == [(1, "a"), (2, "B"), (3, "c")]
            assert [r[0] for r in self._rows(project, "inc_microbatch", "id")] == [1, 2, 3]
            snap = self._rows(project, "snap", "id, v, dbt_valid_to")
            assert [(i, v) for i, v, _ in snap] == [(1, "a"), (2, "b"), (2, "B"), (3, "c")]
            assert [to is None for _, _, to in snap] == [True, False, True, True]
            ids = project.run_sql(
                f"select dbt_scd_id from {project.test_schema}.snap", fetch="all"
            )
            assert len({r[0] for r in ids}) == 4 and all(len(r[0]) == 32 for r in ids)
