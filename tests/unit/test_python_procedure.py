"""A Python model runs inside IRIS as the body of CREATE PROCEDURE ... LANGUAGE PYTHON. IRIS
re-indents every line of that body and has trouble with comment lines, so the model's code is
sent as one base64 line and run with exec: no line of the model reaches IRIS's compiler."""
import base64
import unittest

from dbt.adapters.iris.impl import python_procedure_body

CODE = 'x = 1  # note\ntext = """first\n# not a comment\n    indented"""\ndef f():\n    return 2\n'


class TestPythonProcedureBody(unittest.TestCase):
    def test_body_is_three_unindented_lines(self):
        lines = python_procedure_body(CODE, "s.m").splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "import base64")
        self.assertTrue(lines[1].startswith("exec(compile(base64.b64decode("))
        self.assertEqual(lines[2], 'return "OK"')

    def test_model_code_round_trips_exactly(self):
        line = python_procedure_body(CODE, "s.m").splitlines()[1]
        encoded = line.split('b64decode("', 1)[1].split('")', 1)[0]
        self.assertEqual(base64.b64decode(encoded).decode("utf-8"), CODE)

    def test_no_hash_or_newline_reaches_iris(self):
        body = python_procedure_body(CODE, "s.m")
        self.assertNotIn("#", body)
        self.assertNotIn('"""', body)

    def test_non_ascii_survives(self):
        code = 'name = "Søren ✓"\n'
        line = python_procedure_body(code, "s.m").splitlines()[1]
        encoded = line.split('b64decode("', 1)[1].split('")', 1)[0]
        self.assertEqual(base64.b64decode(encoded).decode("utf-8"), code)


class TestGlueEndsWithoutReturn(unittest.TestCase):
    def test_py_write_table_no_longer_returns(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2]
            / "dbt/include/iris/macros/materializations/table.sql"
        ).read_text()
        body = text[
            text.index("macro py_write_table") : text.index(
                "endmacro", text.index("macro py_write_table")
            )
        ]
        self.assertNotIn('return "OK"', body)
