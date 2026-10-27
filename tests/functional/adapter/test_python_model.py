import os

import pytest

from dbt.tests.adapter.python_model.test_python_model import BasePythonModelTests

# Python models run inside IRIS, so the server's Python needs pandas and
# sqlalchemy-iris installed (see the Dockerfile).
pytestmark = pytest.mark.skipif(
    os.getenv("DBT_IRIS_PYTHON_MODELS") != "1",
    reason="set DBT_IRIS_PYTHON_MODELS=1 when pandas and sqlalchemy-iris are installed in IRIS",
)


class TestPythonModelIRIS(BasePythonModelTests):
    pass


# The incremental materialization supports SQL only.
# class TestPythonIncrementalIRIS(BasePythonIncrementalTests):
#     pass


_hash_in_string = '''
def model(dbt, session):
    import pandas as pd

    # a real comment, removed before the code reaches IRIS
    text = """first line
# not a comment
last"""
    lines = text.splitlines()
    return pd.DataFrame({"n": [len(lines)], "line2": [lines[1]]})
'''


class TestPythonModelKeepsHashLinesInStrings:
    """1.9.x removed every line starting with '#', including lines inside string literals."""

    @pytest.fixture(scope="class")
    def models(self):
        return {"hash_in_string.py": _hash_in_string}

    def test_string_survives(self, project):
        from dbt.tests.util import run_dbt

        run_dbt(["run"])
        n, line2 = project.run_sql(
            f"select n, line2 from {project.test_schema}.hash_in_string", fetch="one"
        )
        assert (n, line2) == (3, "# not a comment")
