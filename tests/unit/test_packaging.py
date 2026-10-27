"""The wheel ships only dbt-iris. intersystems-irispython owns iris/__init__.py; a
second copy in this wheel replaces it on install and deletes it on uninstall."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVER_PACKAGES = ("iris", "intersystems_iris", "irisnative")


def _setup_packages_include():
    tree = ast.parse((ROOT / "setup.py").read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "find_namespace_packages"
        ):
            for kw in node.keywords:
                if kw.arg == "include":
                    return ast.literal_eval(kw.value)
    raise AssertionError("setup.py has no find_namespace_packages(include=...)")


class TestWheelContents(unittest.TestCase):
    def test_setup_includes_only_dbt_packages(self):
        self.assertEqual(_setup_packages_include(), ["dbt", "dbt.*"])

    def test_build_script_does_not_copy_a_driver_into_the_tree(self):
        script = (ROOT / "scripts" / "build-dist.sh").read_text()
        for name in DRIVER_PACKAGES:
            self.assertNotIn(f'"{name}"', script)

    def test_nothing_installs_the_3x_driver_wheel(self):
        self.assertFalse((ROOT / "requirements-iris.txt").exists())
        for path in ("tox.ini", ".github/workflows/main.yml"):
            self.assertNotIn("requirements-iris.txt", (ROOT / path).read_text(), path)


def _setup_call_kw(name):
    tree = ast.parse((ROOT / "setup.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "setup":
            for kw in node.keywords:
                if kw.arg == name:
                    return ast.literal_eval(kw.value)
    return None


class TestRelease200(unittest.TestCase):
    def test_version_is_2_0_0(self):
        attrs = {}
        exec((ROOT / "dbt/adapters/iris/__version__.py").read_text(), attrs)
        self.assertEqual(attrs["version"], "2.0.0")

    def test_install_requires(self):
        self.assertEqual(
            sorted(_setup_call_kw("install_requires")),
            sorted(
                [
                    "dbt-adapters>=1.15.2,<2.0",
                    "dbt-common>=1.22.0,<2.0",
                    "dbt-core>=1.10.0",
                    "intersystems-irispython>=5.4.0",
                ]
            ),
        )

    def test_no_driver_extras(self):
        self.assertFalse(_setup_call_kw("extras_require"))

    def test_pypi_page_is_the_readme_in_markdown(self):
        text = (ROOT / "setup.py").read_text()
        self.assertIn('long_description_content_type="text/markdown"', text)
        self.assertIn("README.md", text)
        self.assertIn("README.md", (ROOT / "MANIFEST.in").read_text())

    def test_python_versions(self):
        self.assertEqual(_setup_call_kw("python_requires"), ">=3.10")

    def test_requirements_dev_installs_from_releases(self):
        text = (ROOT / "requirements-dev.txt").read_text()
        self.assertNotIn("git+", text)
        for name in ("dbt-core", "dbt-tests-adapter"):
            self.assertIn(name, text)

    def test_changelog_has_the_release_and_its_breaking_changes(self):
        text = (ROOT / "CHANGELOG.md").read_text()
        self.assertIn("## 2.0.0", text)
        section = text.split("## 2.0.0", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Breaking", section)
        self.assertIn("vendored", section)
        self.assertIn("dbt-core 1.10", section)


if __name__ == "__main__":
    unittest.main()
