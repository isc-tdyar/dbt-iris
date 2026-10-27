"""materialized_view on IRIS (no materialized views on any IRIS build yet). By default the model is
built as a table, rebuilt on every dbt run, and one warning per run lists the models left on that
default. ``iris_materialized_view_as: view`` builds it as a view instead; ``table`` keeps the
default without the warning; anything else fails before any SQL runs.
"""
import pytest

from dbt.tests.util import run_dbt, run_dbt_and_capture, write_file

_base = "{{ config(materialized='table') }} select 1 as id union all select 2"
_mv = """
{{ config(materialized='materialized_view', on_configuration_change='apply') }}
select count(*) as n from {{ ref('base') }}
"""
_WARNING = "IRIS has no materialized views"


def _kind(project, name):
    (kind,) = project.run_sql(
        "select table_type from information_schema.tables "
        f"where table_schema = '{project.test_schema}' and table_name = '{name}'",
        fetch="one",
    )
    return kind


def _count(project, name="mv"):
    (n,) = project.run_sql(f"select n from {project.test_schema}.{name}", fetch="one")
    return n


class TestMaterializedViewAsTable:
    @pytest.fixture(scope="class")
    def models(self):
        return {"base.sql": _base, "mv.sql": _mv, "mv_two.sql": _mv}

    def test_built_as_a_table_and_refreshed_each_run(self, project):
        results, log = run_dbt_and_capture(["run"])
        assert len(results) == 3
        assert log.count(_WARNING) == 1
        assert "mv, mv_two" in log
        assert _count(project) == 2
        assert _kind(project, "mv") == "BASE TABLE"

        project.run_sql(f"insert into {project.test_schema}.base (id) select 3")
        assert _count(project) == 2  # not refreshed until dbt runs
        run_dbt(["run", "--select", "mv"])
        assert _count(project) == 3


class TestMaterializedViewTableSetExplicitly:
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"models": {"+iris_materialized_view_as": "table"}}

    @pytest.fixture(scope="class")
    def models(self):
        return {"base.sql": _base, "mv.sql": _mv}

    def test_no_warning(self, project):
        _, log = run_dbt_and_capture(["run"])
        assert _WARNING not in log
        assert _kind(project, "mv") == "BASE TABLE"


class TestMaterializedViewAsView:
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"models": {"+iris_materialized_view_as": "view"}}

    @pytest.fixture(scope="class")
    def models(self):
        return {"base.sql": _base, "mv.sql": _mv}

    def test_built_as_a_view_that_follows_its_source(self, project):
        _, log = run_dbt_and_capture(["run"])
        assert _WARNING not in log
        assert _kind(project, "mv") == "VIEW"
        project.run_sql(f"insert into {project.test_schema}.base (id) select 3")
        assert _count(project) == 3


class TestMaterializedViewSwitchesBetweenModes:
    @pytest.fixture(scope="class")
    def models(self):
        return {"base.sql": _base, "mv.sql": _mv}

    def test_table_then_view_then_table(self, project):
        run_dbt(["run"])
        assert _kind(project, "mv") == "BASE TABLE"
        write_file(
            "{{ config(materialized='materialized_view', iris_materialized_view_as='view') }}"
            " select count(*) as n from {{ ref('base') }}",
            project.project_root,
            "models",
            "mv.sql",
        )
        run_dbt(["run", "--select", "mv"])
        assert _kind(project, "mv") == "VIEW"
        assert _count(project) == 2
        write_file(_mv, project.project_root, "models", "mv.sql")
        run_dbt(["run", "--select", "mv"])
        assert _kind(project, "mv") == "BASE TABLE"
        assert _count(project) == 2


class TestMaterializedViewInvalidSetting:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "base.sql": _base,
            "mv.sql": "{{ config(materialized='materialized_view', iris_materialized_view_as='incremental') }}"
            " select count(*) as n from {{ ref('base') }}",
        }

    def test_fails_listing_the_allowed_values(self, project):
        results, log = run_dbt_and_capture(["run"], expect_pass=False)
        failed = [r for r in results if r.status == "error"]
        assert [r.node.name for r in failed] == ["mv"]
        assert "iris_materialized_view_as" in log
        assert "'table'" in log and "'view'" in log
        (n,) = project.run_sql(
            "select count(*) from information_schema.tables "
            f"where table_schema = '{project.test_schema}' and table_name = 'mv'",
            fetch="one",
        )
        assert n == 0
