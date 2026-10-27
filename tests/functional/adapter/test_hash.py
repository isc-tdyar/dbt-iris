"""The native hash() gives the same text as the 1.9.x Embedded Python hash() (spec 18 FR-13, FR-14).

Snapshot tables keep the dbt_scd_id values written by 1.9.x, so a different result for the same
input would split their history. The old function is created here under another name; the test
is skipped where Embedded Python is not available to run it.
"""
import pytest

_OLD = """
CREATE OR REPLACE FUNCTION DBT_TEST_HASH_PY(alg VARCHAR(''), str VARCHAR(''))
PROCEDURE
RETURNS VARCHAR(1024)
LANGUAGE PYTHON
{{
  import hashlib
  return hashlib.new(alg, str.encode()).hexdigest()
}}
"""  # doubled braces: project.run_sql applies str.format

_INPUTS = ["abc", "", "é漢字 ✓", "x" * 5000, "123.45", "line\nbreak", "  padded  "]


def _create_hash(project):
    with project.adapter.connection_named("__test_hash"):
        project.adapter.execute_macro("create_function_hash", kwargs={})


class TestHashMatchesPython:
    @pytest.fixture(scope="class")
    def models(self):
        return {"dummy.sql": "select 1 as id"}

    def test_same_text(self, project):
        _create_hash(project)
        try:
            project.run_sql(_OLD)
            project.run_sql("select DBT_TEST_HASH_PY('md5', 'abc')", fetch="one")
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Embedded Python not available to run the 1.9.x function: {e}")
        for alg in ("md5", "sha256"):
            for value in _INPUTS:
                new, old = self._pair(project, alg, value)
                assert new == old, (alg, value[:20], new, old)
                assert len(new) == (32 if alg == "md5" else 64)
                assert new == new.lower()

    def test_null_gives_null(self, project):
        _create_hash(project)
        (value,) = project.run_sql("select HASH('md5', cast(null as varchar(10)))", fetch="one")
        assert value is None

    @staticmethod
    def _pair(project, alg, value):
        literal = value.replace("'", "''")
        return project.run_sql(
            f"select HASH('{alg}', '{literal}'), DBT_TEST_HASH_PY('{alg}', '{literal}')",
            fetch="one",
        )


class TestHashWithoutEmbeddedPython:
    """Runs everywhere: the native function needs nothing from Embedded Python."""

    @pytest.fixture(scope="class")
    def models(self):
        return {"dummy.sql": "select 1 as id"}

    def test_known_digests(self, project):
        _create_hash(project)
        (md5,) = project.run_sql("select HASH('md5', 'abc')", fetch="one")
        (sha,) = project.run_sql("select HASH('sha256', 'abc')", fetch="one")
        assert md5 == "900150983cd24fb0d6963f7d28e17f72"
        assert sha == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
