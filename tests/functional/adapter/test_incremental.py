import re

import pytest
from dbt.tests.adapter.incremental.test_incremental_merge_exclude_columns import (
    BaseMergeExcludeColumns,
)
from dbt.tests.adapter.incremental.test_incremental_on_schema_change import (
    BaseIncrementalOnSchemaChange,
)
from dbt.tests.adapter.incremental.test_incremental_predicates import BaseIncrementalPredicates
from dbt.tests.adapter.incremental import test_incremental_unique_id as unique_id
from dbt.tests.adapter.incremental.test_incremental_unique_id import BaseIncrementalUniqueKey


class TestBaseMergeExcludeColumns(BaseMergeExcludeColumns):
    pass


class TestIncrementalOnSchemaChange(BaseIncrementalOnSchemaChange):
    pass


class TestIncrementalPredicatesDeleteInsert(BaseIncrementalPredicates):
    pass


# dbt's expected tables for these tests mix cast('2022-02-14' as date) with text dates in one
# UNION ALL. IRIS returns the right text from a plain SELECT of that union, but CREATE TABLE AS and
# INSERT ... SELECT store the date's internal day number ('66154'). The fixture below casts every
# branch to DATE, which is what the README tells users to do; TestUnionOfDateAndText records the
# IRIS behaviour itself. Measured on 2026.1, 2026.2, 2026.3.0L.196 and 2027.1.0RCTE.100
# (irispython-dx dxlab/rows_diff_probe3.py, xfail_workaround_probe.py).
_TEXT_DATE = re.compile(r"'(\d{4}-\d{2}-\d{2})'(?=\s*$)", re.MULTILINE)


def _every_branch_a_date(sql):
    return _TEXT_DATE.sub(r"cast('\1' as date)", sql)


class TestIncrementalUniqueKey(BaseIncrementalUniqueKey):
    @pytest.fixture(scope="class")
    def models(self):
        return {
            **{
                f"{name[len('models__'):-len('_sql')]}.sql": sql
                for name, sql in vars(unique_id).items()
                if name.startswith("models__") and not name.startswith("models__expected__")
            },
            "expected": {
                "one_str__overwrite.sql": _every_branch_a_date(
                    unique_id.models__expected__one_str__overwrite_sql
                ),
                "unique_key_list__inplace_overwrite.sql": _every_branch_a_date(
                    unique_id.models__expected__unique_key_list__inplace_overwrite_sql
                ),
            },
        }


class TestUnionOfDateAndText:
    """The IRIS defect behind the fixture above, kept as a strict expected failure so that a fixed
    IRIS build shows up as a failing test with instructions."""

    @pytest.mark.xfail(
        strict=True,
        reason="IRIS defect: CREATE TABLE AS of a UNION ALL with a DATE leg and a VARCHAR leg "
        "stores the date's internal day number ('66154') instead of its text. If this test "
        "XPASSes, this IRIS build is fixed: remove the xfail marker, and say from which IRIS "
        "release in the README's 'UNION of a DATE and text' note.",
    )
    def test_create_table_as_keeps_the_dates_text(self, project):
        t = f"{project.test_schema}.union_dates"
        project.run_sql(
            f"create table {t} as select cast('2022-02-14' as date) as d "
            "union all select '2022-02-15'"
        )
        stored = [r[0] for r in project.run_sql(f"select d from {t} order by d", fetch="all")]
        assert stored == ["2022-02-14", "2022-02-15"], (
            f"CREATE TABLE AS of a DATE/VARCHAR UNION ALL stored {stored}, and "
            "'66154' is the DATE's internal day number for 2022-02-14"
        )
