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


if __name__ == "__main__":
    unittest.main()
