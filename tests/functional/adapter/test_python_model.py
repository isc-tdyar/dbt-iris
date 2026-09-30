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
