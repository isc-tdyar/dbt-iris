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


@pytest.mark.skipif(
    os.environ.get("DBT_IRIS_OVERLAP_TEST") != "1",
    reason="opt-in (DBT_IRIS_OVERLAP_TEST=1): overlapping replaces of one view can leave the IRIS "
    "catalog damaged ('DDL not enabled for class') or the server refusing connections, which "
    "breaks every later test; observed on 2026.1, 2026.2, 2026.3 and 2027.1.0RCTE.100.0",
)
class TestTwoProcessesAtOnce:
    @pytest.fixture(scope="class")
    def models(self):
        return {"stg.sql": _view, "mart.sql": _table, "inc.sql": _incremental}

    def test_two_runs_overlap(self, project):
        """Issue #3's error was a temporary table that already existed. Temporary, intermediate
        and backup names now carry the invocation id, so that cannot recur, and at least one of
        two overlapping runs completes.

        Two runs that replace the same models at once are not made safe: dbt does not support
        overlapping runs of one project (dbt-core #2881), and IRIS reports the clash in several
        ways. Observed on 2026.1 and 2026.2: ERROR #5864 (class open for editing), #5351 (class
        does not exist), #5116 (class dictionary version out of date), and a dependent model
        finding the view missing mid-replace. On 2026.3 only #5864 was seen."""
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
        for out in outputs:
            assert "already exists" not in out, out[-3000:]
