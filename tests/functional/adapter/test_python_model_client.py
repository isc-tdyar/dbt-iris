import os

import pytest

from dbt.tests.adapter.python_model.test_python_model import BasePythonModelTests

# submission_method: client runs the model in the dbt process, so dbt's own Python environment
# needs pandas, sqlalchemy and sqlalchemy-intersystems-iris; nothing is installed in IRIS.
pytestmark = pytest.mark.skipif(
    os.getenv("DBT_IRIS_PYTHON_MODELS_CLIENT") != "1",
    reason="set DBT_IRIS_PYTHON_MODELS_CLIENT=1 when pandas, sqlalchemy and "
    "sqlalchemy-intersystems-iris are installed where dbt runs",
)


class TestPythonModelClientIRIS(BasePythonModelTests):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"models": {"+submission_method": "client"}}


_where = """
def model(dbt, session):
    dbt.config(submission_method="client")
    import sys
    import pandas as pd

    return pd.DataFrame({"python": [sys.executable]})
"""


class TestPythonModelClientRunsInTheDbtProcess:
    @pytest.fixture(scope="class")
    def models(self):
        return {"where_it_ran.py": _where}

    def test_the_model_ran_where_dbt_runs(self, project):
        import sys

        from dbt.tests.util import run_dbt

        run_dbt(["run"])
        (python,) = project.run_sql(
            f"select python from {project.test_schema}.where_it_ran", fetch="one"
        )
        assert python == sys.executable
