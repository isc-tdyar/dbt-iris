"""The microbatch strategy (spec 18 FR-11), on dbt's standard test.

IRIS has no TIMESTAMP '...-0' literal and no multi-row VALUES, so the input model and the
insert use CAST and UNION ALL.
"""
import pytest

from dbt.tests.adapter.incremental.test_incremental_microbatch import BaseMicrobatch

_input_model_sql = """
{{ config(materialized='table', event_time='event_time') }}
select 1 as id, cast('2020-01-01 00:00:00' as timestamp) as event_time
union all
select 2 as id, cast('2020-01-02 00:00:00' as timestamp) as event_time
union all
select 3 as id, cast('2020-01-03 00:00:00' as timestamp) as event_time
"""


class TestMicrobatch(BaseMicrobatch):
    @pytest.fixture(scope="class")
    def input_model_sql(self) -> str:
        return _input_model_sql

    @pytest.fixture(scope="class")
    def insert_two_rows_sql(self, project) -> str:
        relation = project.adapter.Relation.create(
            database=project.database, schema=project.test_schema
        )
        return (
            f"insert into {relation}.input_model (id, event_time) "
            "select 4, cast('2020-01-04 00:00:00' as timestamp) "
            "union all select 5, cast('2020-01-05 00:00:00' as timestamp)"
        )
