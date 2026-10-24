"""Parallel runs (spec 18 FR-17, upstream issue #3).

dbt's standard concurrency test runs one invocation with several threads. Issue #3 is about
several `dbt run` processes on the same project at once: their temporary and backup tables
must not collide.
"""
import os
import subprocess
import sys

import pytest

from dbt.tests.adapter.concurrency.test_concurrency import BaseConcurrency
from dbt.tests.util import run_dbt

_view = """
{{ config(materialized='view') }}
select 1 as id, 'a' as v
"""
_table = """
{{ config(materialized='table') }}
select id, v from {{ ref('stg') }}
"""
_incremental = """
{{ config(materialized='incremental', unique_key='id') }}
select id, v from {{ ref('stg') }}
"""


class TestConcurrency(BaseConcurrency):
    pass


class TestTwoProcessesAtOnce:
    @pytest.fixture(scope="class")
    def models(self):
        return {"stg.sql": _view, "mart.sql": _table, "inc.sql": _incremental}

    def test_two_runs_overlap(self, project):
        """Issue #3's error was a temporary table that already existed. Temporary, intermediate
        and backup names now carry the invocation id, so that cannot recur. Two runs replacing
        the same models can still deadlock on IRIS class locks inside their transactions (dbt
        does not support overlapping runs of one project, dbt-core #2881); when that happens the
        loser fails with the lock error, not a missing or duplicate table, and the winner's
        result is intact."""
        run_dbt(["run"])  # first build, so the second round exercises the swap and backup path
        dbt = os.path.join(os.path.dirname(sys.executable), "dbt")
        args = [
            dbt,
            "run",
            "--project-dir",
            project.project_root,
            "--profiles-dir",
            project.profiles_dir,
        ]
        procs = [
            subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for _ in range(2)
        ]
        outputs = [p.communicate(timeout=600)[0] for p in procs]
        assert any(p.returncode == 0 for p in procs), "\n".join(o[-2000:] for o in outputs)
        for p, out in zip(procs, outputs):
            assert "already exists" not in out, out[-3000:]
            assert "not found" not in out.lower(), out[-3000:]
            if p.returncode != 0:
                assert "open for editing" in out or "exclusive lock" in out, out[-3000:]
        (count,) = project.run_sql(f"select count(*) from {project.test_schema}.mart", fetch="one")
        assert count == 1
