import pytest
from dbt.tests.adapter.incremental.test_incremental_merge_exclude_columns import (
    BaseMergeExcludeColumns,
)
from dbt.tests.adapter.incremental.test_incremental_on_schema_change import (
    BaseIncrementalOnSchemaChange,
)
from dbt.tests.adapter.incremental.test_incremental_predicates import BaseIncrementalPredicates
from dbt.tests.adapter.incremental.test_incremental_unique_id import BaseIncrementalUniqueKey


class TestBaseMergeExcludeColumns(BaseMergeExcludeColumns):
    pass


class TestIncrementalOnSchemaChange(BaseIncrementalOnSchemaChange):
    pass


class TestIncrementalPredicatesDeleteInsert(BaseIncrementalPredicates):
    pass


# dbt's expected tables for these four mix cast('2022-02-14' as date) with text dates in one
# UNION ALL. IRIS returns the right text from a plain SELECT of that union, but CREATE TABLE AS and
# INSERT ... SELECT store the date's internal day number ('66154'), so the expected table is wrong.
# The incremental models themselves are correct. Measured on 2026.2, 2026.3.0L.196 and
# 2027.1.0RCTE.100 (irispython-dx dxlab/rows_diff_probe3.py).
_UNION_DATE = pytest.mark.xfail(
    strict=True,
    reason="IRIS stores a DATE's internal value when CREATE TABLE AS / INSERT SELECT a mixed "
    "DATE and VARCHAR UNION ALL; dbt's expected table is built that way",
)


class TestIncrementalUniqueKey(BaseIncrementalUniqueKey):
    @_UNION_DATE
    def test__one_unique_key(self, project):
        super().test__one_unique_key(project)

    @_UNION_DATE
    def test__unary_unique_key_list(self, project):
        super().test__unary_unique_key_list(project)

    @_UNION_DATE
    def test__duplicated_unary_unique_key_list(self, project):
        super().test__duplicated_unary_unique_key_list(project)

    @_UNION_DATE
    def test__trinary_unique_key_list(self, project):
        super().test__trinary_unique_key_list(project)
