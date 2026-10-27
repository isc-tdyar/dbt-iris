"""Result rows are copied out of the cursor before dbt reads them."""
import unittest


class _LiveRow:
    """Mimics irispython 5.x DataRow: a proxy that dies when its cursor closes."""

    def __init__(self, cursor, values):
        self._cursor, self._values = cursor, values

    def __iter__(self):
        if self._cursor.closed:
            raise RuntimeError("Cursor closed; DataRow is inaccessible")
        return iter(self._values)

    def __getitem__(self, i):
        if self._cursor.closed:
            raise RuntimeError("Cursor closed; DataRow is inaccessible")
        return self._values[i]


class _Cursor:
    def __init__(self, rows):
        self.closed = False
        self.description = [("id",), ("name",)]
        self._rows = [_LiveRow(self, r) for r in rows]

    def fetchall(self):
        return self._rows

    def fetchmany(self, n):
        return self._rows[:n]

    def close(self):
        self.closed = True


class TestResultsDetachFromCursor(unittest.TestCase):
    """dbt reads result rows after the adapter has closed the cursor. With the
    compiled driver, rows are live proxies, so they must be copied out first."""

    def test_rows_survive_cursor_close(self):
        from dbt.adapters.iris.connections import IRISConnectionManager

        cur = _Cursor([(1, "a"), (2, "b")])
        table = IRISConnectionManager.get_result_from_cursor(cur, None)
        cur.close()
        self.assertEqual([tuple(r) for r in table.rows], [(1, "a"), (2, "b")])

    def test_limit_uses_fetchmany(self):
        from dbt.adapters.iris.connections import IRISConnectionManager

        cur = _Cursor([(1, "a"), (2, "b"), (3, "c")])
        table = IRISConnectionManager.get_result_from_cursor(cur, 2)
        cur.close()
        self.assertEqual(len(table.rows), 2)
