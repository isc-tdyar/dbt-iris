"""Release documentation (spec 18 FR-22, FR-23)."""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text()
SETUP_PAGE = ROOT / "docs" / "dbt-docs-site" / "iris-setup.md"
CONFIGS_PAGE = ROOT / "docs" / "dbt-docs-site" / "iris-configs.md"


class TestProfileTemplate(unittest.TestCase):
    def test_dbt_init_prompts_for_the_connection(self):
        template = yaml.safe_load((ROOT / "dbt/include/iris/profile_template.yml").read_text())
        self.assertEqual(template["fixed"]["type"], "iris")
        for key in ("hostname", "port", "database", "username", "password", "schema"):
            self.assertIn(key, template["prompts"], key)


class TestDocsSitePages(unittest.TestCase):
    def test_setup_page_lists_every_connection_setting(self):
        text = SETUP_PAGE.read_text()
        for key in (
            "hostname",
            "port",
            "database",
            "namespace",
            "username",
            "password",
            "schema",
            "threads",
        ):
            self.assertIn(key, text, key)
        self.assertIn("pip install dbt-iris", text)
        self.assertIn("dbt debug", text)

    def test_configs_page_covers_every_strategy_and_the_capability_checks(self):
        from dbt.adapters.iris.impl import IRISAdapter

        text = CONFIGS_PAGE.read_text()
        for strategy in IRISAdapter.valid_incremental_strategies(None):
            self.assertIn(f"`{strategy}`", text, strategy)
        self.assertIn("WITH RECURSIVE", text)
        self.assertIn("MERGE", text)
        self.assertIn("Embedded Python", text)

    def test_community_list_entry(self):
        text = (ROOT / "docs" / "dbt-docs-site" / "community-adapters-entry.md").read_text()
        self.assertIn("dbt-iris", text)
        self.assertIn("InterSystems IRIS", text)


class TestReleaseChecklist(unittest.TestCase):
    def test_checklist_covers_the_dbt_guide(self):
        text = (ROOT / "docs" / "release-checklist.md").read_text()
        for needle in (
            "community adapters",
            "iris-setup.md",
            "iris-configs.md",
            "Security practices",
            "PyPI",
        ):
            self.assertIn(needle, text, needle)


class TestReadme(unittest.TestCase):
    def test_states_supported_versions_and_setup(self):
        for needle in (
            "dbt-core 1.10",
            "intersystems-irispython",
            "Python 3.10",
            "Python models",
            "2.0.0",
        ):
            self.assertIn(needle, README, needle)

    def test_strategies_and_limits(self):
        from dbt.adapters.iris.impl import IRISAdapter

        for strategy in IRISAdapter.valid_incremental_strategies(None):
            self.assertIn(f"`{strategy}`", README, strategy)
        self.assertIn("WITH RECURSIVE", README)
        self.assertIn("overlapping", README)

    def test_no_internal_ticket_keys(self):
        self.assertIsNone(re.search(r"\bDP-\d{5,}", README))

    def test_links_the_docs_site_pages(self):
        self.assertIn("iris-setup", README)
        self.assertIn("iris-configs", README)


class TestIssue7DockerFiles(unittest.TestCase):
    def test_dockerfile_pins_a_tag_that_exists(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertRegex(dockerfile, r"iris-community:\w")
        self.assertNotRegex(dockerfile, r"iris-community\s*$")

    def test_readme_compose_matches_the_repository(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        block = re.search(r"```yml\n(version:.*?|services:.*?)```", README, re.S)
        self.assertIsNotNone(block)
        self.assertEqual(yaml.safe_load(block.group(1)), yaml.safe_load(compose))

    def test_compose_needs_no_licence_key(self):
        self.assertNotIn("iris.key", (ROOT / "docker-compose.yml").read_text())


if __name__ == "__main__":
    unittest.main()
