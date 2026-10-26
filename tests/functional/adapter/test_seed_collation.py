"""Seeds and iris_collation. IRIS string columns default to a case-insensitive collation:
GROUP BY returns the upper-case form ('FEMALE') and 'female' = 'Female'. With
iris_collation: exact, seed string columns keep their case in GROUP BY and compare
case-sensitively, as on other warehouses, and a table built from the seed inherits that.
"""
import pytest

from dbt.tests.util import run_dbt

_seed = """id,gender
1,Male
2,Female
3,Male
"""
_by_gender = """
{{ config(materialized='table') }}
select gender, count(*) as ct from {{ ref('people') }} group by gender
"""
_copy = "{{ config(materialized='table') }} select * from {{ ref('people') }}"


def _groups(project, relation):
    rows = project.run_sql(
        f"select gender, count(*) from {project.test_schema}.{relation} group by gender",
        fetch="all",
    )
    return sorted(tuple(r) for r in rows)


def _matches_lower_case(project, relation):
    (n,) = project.run_sql(
        f"select count(*) from {project.test_schema}.{relation} where gender = 'female'",
        fetch="one",
    )
    return n


class _Base:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {"people.csv": _seed}

    @pytest.fixture(scope="class")
    def models(self):
        return {"by_gender.sql": _by_gender, "people_copy.sql": _copy}


class TestSeedCollationDefault(_Base):
    def test_group_by_returns_upper_case_and_equality_ignores_case(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        assert _groups(project, "people") == [("FEMALE", 1), ("MALE", 2)]
        assert _matches_lower_case(project, "people") == 1


class TestSeedCollationExact(_Base):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"seeds": {"+iris_collation": "exact"}}

    def test_group_by_keeps_case_and_equality_is_case_sensitive(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        assert _groups(project, "people") == [("Female", 1), ("Male", 2)]
        assert _matches_lower_case(project, "people") == 0
        (row,) = project.run_sql(
            f"select gender, ct from {project.test_schema}.by_gender where ct = 1", fetch="all"
        )
        assert tuple(row) == ("Female", 1)

    def test_a_table_built_from_the_seed_inherits_it(self, project):
        run_dbt(["seed"])
        run_dbt(["run"])
        assert _groups(project, "people_copy") == [("Female", 1), ("Male", 2)]
        assert _matches_lower_case(project, "people_copy") == 0


class TestSeedCollationBadValue(_Base):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"seeds": {"+iris_collation": "upper"}}

    def test_fails_before_creating_the_seed(self, project):
        results = run_dbt(["seed"], expect_pass=False)
        assert "iris_collation" in results[0].message
