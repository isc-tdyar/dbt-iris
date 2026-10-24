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
