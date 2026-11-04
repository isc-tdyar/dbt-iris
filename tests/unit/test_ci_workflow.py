"""The GitHub Actions workflow (spec 18 FR-19, FR-20)."""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/main.yml").read_text())
JOBS = WORKFLOW["jobs"]
PYTHONS = ["3.10", "3.11", "3.12"]
DBT_MINORS = ["1.11", "1.12"]


def _run_text(job):
    return "\n".join(step.get("run", "") for step in job.get("steps", []))


class TestFunctionalJob(unittest.TestCase):
    job = JOBS["functional"]

    def test_matrix(self):
        matrix = self.job["strategy"]["matrix"]
        self.assertEqual(matrix["python"], PYTHONS)
        self.assertEqual(matrix["dbt-core"], DBT_MINORS)
        self.assertTrue(matrix["image"])
        for image in matrix["image"]:
            self.assertTrue(
                image.startswith("containers.intersystems.com/intersystems/iris-community:"), image
            )

    def test_iris_runs_as_a_service_not_through_testcontainers(self):
        service = self.job["services"]["iris"]
        self.assertEqual(service["image"], "${{ matrix.image }}")
        self.assertIn("1972:1972", service["ports"])
        text = _run_text(self.job)
        self.assertNotIn("--container", text)
        self.assertNotIn("testcontainers", text)

    def test_passwords_unexpired_and_suite_pointed_at_the_service(self):
        text = _run_text(self.job)
        self.assertIn("UnExpireUserPasswords", text)
        env = {}
        for step in self.job["steps"]:
            env.update(step.get("env", {}))
        env.update(self.job.get("env", {}))
        self.assertEqual(env.get("DBT_IRIS_HOST"), "localhost")
        self.assertIn("tests/functional", text)
        self.assertIn("dbt-core~=${{ matrix.dbt-core }}.0", text)


class TestPythonModelsJob(unittest.TestCase):
    job = JOBS["python-models"]

    def test_installs_into_iris_python_and_enables_the_test(self):
        text = _run_text(self.job)
        self.assertIn("mgr/python", text)
        for package in ("pandas", "sqlalchemy-iris"):
            self.assertIn(package, text)
        env = {}
        for step in self.job["steps"]:
            env.update(step.get("env", {}))
        env.update(self.job.get("env", {}))
        self.assertEqual(str(env.get("DBT_IRIS_PYTHON_MODELS")), "1")


def _env(job):
    env = dict(job.get("env", {}))
    for step in job.get("steps", []):
        env.update(step.get("env", {}))
    return env


class TestPythonModelsClientJob(unittest.TestCase):
    """submission_method: client runs the model where dbt runs, over the official dialect."""

    job = JOBS.get("python-models-client", {})

    def test_installs_where_dbt_runs_and_enables_the_test(self):
        text = _run_text(self.job)
        self.assertNotIn("mgr/python", text)
        for package in ("pandas", "sqlalchemy-intersystems-iris"):
            self.assertIn(package, text)
        self.assertEqual(str(_env(self.job).get("DBT_IRIS_PYTHON_MODELS_CLIENT")), "1")
        self.assertIn("tests/functional/adapter/test_python_model_client.py", text)


class TestDxJob(unittest.TestCase):
    """driver: dx, the irispython-dx layer, over the whole suite and both Python-model modes."""

    job = JOBS.get("dx", {})

    def test_runs_only_when_a_layer_wheel_is_configured(self):
        # The layer is not on PyPI yet; the wheel's URL is a repository variable.
        self.assertIn("vars.IRISPYTHON_DX_WHEEL", str(self.job.get("if", "")))

    def test_the_layer_goes_where_dbt_runs_and_into_iris_python(self):
        text = _run_text(self.job)
        self.assertIn("IRISPYTHON_DX_WHEEL", text)
        self.assertIn("mgr/python", text)
        self.assertIn("sqlalchemy-intersystems-iris", text)
        self.assertIn("tests/functional", text)

    def test_selects_the_dx_driver_and_both_python_model_modes(self):
        env = _env(self.job)
        self.assertEqual(env.get("DBT_IRIS_DRIVER"), "dx")
        self.assertEqual(str(env.get("DBT_IRIS_PYTHON_MODELS")), "1")
        self.assertEqual(str(env.get("DBT_IRIS_PYTHON_MODELS_CLIENT")), "1")


class TestExampleJob(unittest.TestCase):
    """The tutorial's project, examples/jaffle_shop, builds against IRIS on every change."""

    job = JOBS.get("example", {})

    def test_iris_runs_as_a_service(self):
        service = self.job["services"]["iris"]
        self.assertEqual(
            service["image"], "containers.intersystems.com/intersystems/iris-community:latest-cd"
        )
        self.assertIn("1972:1972", service["ports"])
        self.assertIn("UnExpireUserPasswords", _run_text(self.job))

    def test_installs_the_adapter_and_builds_the_example_twice(self):
        text = _run_text(self.job)
        self.assertIn("pip install -e .", text)
        builds = [line for line in text.splitlines() if "dbt build" in line]
        self.assertEqual(len(builds), 2, builds)
        for line in builds:
            self.assertIn("examples/jaffle_shop", line)

    def test_profile_comes_from_the_environment(self):
        env = dict(self.job.get("env", {}))
        for step in self.job["steps"]:
            env.update(step.get("env", {}))
        self.assertEqual(env.get("DBT_IRIS_HOST"), "localhost")
        self.assertEqual(str(env.get("DBT_IRIS_PORT")), "1972")
        profile = yaml.safe_load((ROOT / "examples/jaffle_shop/profiles.yml").read_text())
        dev = profile["jaffle_shop"]["outputs"]["dev"]
        for key, var in (("hostname", "DBT_IRIS_HOST"), ("username", "DBT_IRIS_USER")):
            self.assertIn(f"env_var('{var}'", str(dev[key]), key)

    def test_the_build_waits_for_it(self):
        self.assertIn("example", JOBS["build"]["needs"])


class TestCodeQualityJob(unittest.TestCase):
    def test_supported_pythons_only(self):
        text = yaml.safe_dump(JOBS["code-quality"])
        self.assertNotIn("3.9", text)
        self.assertIn("py310,py311,py312", _run_text(JOBS["code-quality"]))

    def test_build_checks_the_wheel(self):
        text = _run_text(JOBS["build"])
        self.assertIn("twine check", text)
        self.assertIn("check-wheel-contents", text)


class TestTox(unittest.TestCase):
    def test_envlist(self):
        text = (ROOT / "tox.ini").read_text()
        self.assertIn("py3{10,11,12}", text)
        self.assertNotIn("py39", text)


if __name__ == "__main__":
    unittest.main()
