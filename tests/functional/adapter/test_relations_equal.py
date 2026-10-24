"""dbt's test helper check_relations_equal must be able to fail.

1.9.x's get_rows_different_sql returned "SELECT 0,0", so every relation comparison in dbt's
standard suites passed whatever the data. This control checks a real difference is caught,
and that the comparison is neither looser nor stricter than the data: IRIS's bare EXCEPT
ignores case, never matches a TEXT (stream) column, and compares a DATE with a VARCHAR by
the DATE's internal value.
"""
import pytest

from dbt.tests.util import check_relations_equal, run_dbt

_a = "{{ config(materialized='table') }} select 1 as id, 'x' as v union all select 2, 'y'"
_same = "{{ config(materialized='table') }} select 2 as id, 'y' as v union all select 1, 'x'"
_other_value = (
    "{{ config(materialized='table') }} select 1 as id, 'x' as v union all select 2, 'z'"
)
_extra_row = "{{ config(materialized='table') }} select 1 as id, 'x' as v union all select 2, 'y' union all select 3, 'w'"
_other_case = "{{ config(materialized='table') }} select 1 as id, 'X' as v union all select 2, 'y'"
_with_null = "{{ config(materialized='table') }} select 1 as id, cast(null as varchar(5)) as v"
_as_date = "{{ config(materialized='table') }} select 1 as id, cast('2020-02-12' as date) as d"
_as_text = "{{ config(materialized='table') }} select 1 as id, '2020-02-12' as d"

_text_seed_csv = "id,v\n1,x\n2,y\n"
_seed_props = """
version: 2
seeds:
  - name: text_seed
    config:
      column_types:
        id: integer
        v: text
"""


class TestRelationsEqualCanFail:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "a.sql": _a,
            "same.sql": _same,
            "other_value.sql": _other_value,
            "extra_row.sql": _extra_row,
            "other_case.sql": _other_case,
            "with_null.sql": _with_null,
            "with_null_too.sql": _with_null,
            "as_date.sql": _as_date,
            "as_text.sql": _as_text,
        }

    @pytest.fixture(scope="class")
    def seeds(self):
        return {"text_seed.csv": _text_seed_csv, "properties.yml": _seed_props}

    def test_equal_and_different(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        check_relations_equal(project.adapter, ["a", "same"])
        with pytest.raises(AssertionError):
            check_relations_equal(project.adapter, ["a", "other_value"])
        with pytest.raises(AssertionError):
            check_relations_equal(project.adapter, ["a", "extra_row"])

    def test_case_is_a_difference(self, project):
        run_dbt(["run", "--select", "a", "other_case"])
        with pytest.raises(AssertionError):
            check_relations_equal(project.adapter, ["a", "other_case"])

    def test_nulls_match(self, project):
        run_dbt(["run", "--select", "with_null", "with_null_too"])
        check_relations_equal(project.adapter, ["with_null", "with_null_too"])

    def test_text_column_matches_varchar_with_same_content(self, project):
        run_dbt(["seed"])
        run_dbt(["run", "--select", "a"])
        check_relations_equal(project.adapter, ["text_seed", "a"])

    def test_date_matches_its_odbc_text(self, project):
        run_dbt(["run", "--select", "as_date", "as_text"])
        check_relations_equal(project.adapter, ["as_date", "as_text"])
