"""insert_overwrite is not offered (spec 18 FR-12)."""
import pytest

from dbt.tests.util import run_dbt

_model = """
{{ config(materialized='incremental', incremental_strategy='insert_overwrite') }}
select 1 as id
"""


class TestInsertOverwriteRefused:
    @pytest.fixture(scope="class")
    def models(self):
        return {"overwrite_model.sql": _model}

    def test_refused(self, project):
        results = run_dbt(["run"], expect_pass=False)
        assert "insert_overwrite" in results.results[0].message
        assert "not valid" in results.results[0].message
