"""Connect-time capability checks (spec 18 FR-9, FR-15).

The adapter asks the server, once per server, whether it accepts MERGE and WITH RECURSIVE, and
caches the answer. A statement that uses WITH RECURSIVE on a server that does not accept it is
refused before execution with a message naming the capability.
"""
import unittest

from dbt_common.exceptions import DbtRuntimeError

from dbt.adapters.iris import capabilities as caps


class _Cursor:
    def __init__(self, outcomes, log):
        self._outcomes, self._log = outcomes, log

    def execute(self, sql, *args):
        self._log.append(sql)
        for key, outcome in self._outcomes.items():
            if key in sql.upper():
                if isinstance(outcome, Exception):
                    raise outcome
                return
        return

    def fetchall(self):
        return [(1,), (2,)]

    def close(self):
        pass


class _Handle:
    def __init__(self, outcomes):
        self.log = []
        self._outcomes = outcomes

    def cursor(self):
        return _Cursor(self._outcomes, self.log)


def _err(code, text="x"):
    return Exception("<SQL ERROR>; Details: [SQLCODE: <%d>:<%s>]" % (code, text))


class TestProbes(unittest.TestCase):
    def test_merge_refused_as_syntax_means_unsupported(self):
        self.assertFalse(caps.probe_merge(_Handle({"MERGE": _err(-51, "SQL statement expected")})))

    def test_merge_reaching_table_lookup_means_supported(self):
        self.assertTrue(caps.probe_merge(_Handle({"MERGE": _err(-30, "Table or view not found")})))

    def test_merge_running_means_supported(self):
        self.assertTrue(caps.probe_merge(_Handle({})))

    def test_recursive_runs_means_supported(self):
        self.assertTrue(caps.probe_recursive_cte(_Handle({})))

    def test_recursive_error_means_unsupported(self):
        self.assertFalse(
            caps.probe_recursive_cte(_Handle({"RECURSIVE": _err(-400, "Fatal error occurred")}))
        )

    def test_probes_leave_no_objects_behind(self):
        handle = _Handle({"MERGE": _err(-30)})
        caps.probe_merge(handle)
        self.assertFalse(
            any(s.upper().startswith(("CREATE", "DROP", "INSERT")) for s in handle.log)
        )


class TestCache(unittest.TestCase):
    def setUp(self):
        caps.clear_cache()

    def test_each_server_is_probed_once(self):
        handle = _Handle({"RECURSIVE": _err(-400)})
        key = ("h", 1972, "USER")
        self.assertFalse(caps.supports(key, handle, "recursive_cte"))
        self.assertFalse(caps.supports(key, handle, "recursive_cte"))
        self.assertEqual(sum("RECURSIVE" in s.upper() for s in handle.log), 1)

    def test_servers_are_cached_separately(self):
        caps.supports(("a", 1, "U"), _Handle({"RECURSIVE": _err(-400)}), "recursive_cte")
        self.assertTrue(caps.supports(("b", 1, "U"), _Handle({}), "recursive_cte"))

    def test_unknown_capability(self):
        with self.assertRaises(KeyError):
            caps.supports(("h", 1, "U"), _Handle({}), "time_travel")


class TestRecursiveCheck(unittest.TestCase):
    SQL = "create table x as WITH RECURSIVE r(n) AS (select 1 union all select n+1 from r where n<3) select n from r"

    def test_refused_with_a_plain_message(self):
        with self.assertRaises(DbtRuntimeError) as ctx:
            caps.check_statement(self.SQL, lambda name: False)
        msg = str(ctx.exception)
        self.assertIn("WITH RECURSIVE", msg)
        self.assertIn("IRIS", msg)
        self.assertNotIn("SQLCODE", msg)

    def test_allowed_when_supported(self):
        caps.check_statement(self.SQL, lambda name: True)

    def test_statement_without_recursion_never_asks(self):
        def ask(name):
            raise AssertionError("should not probe")

        caps.check_statement("with a as (select 1 as n) select n from a", ask)
        caps.check_statement("select 'with recursive' as label", ask)

    def test_case_and_whitespace(self):
        self.assertTrue(caps.uses_recursive_cte("WITH\n  recursive r AS (select 1) select 1"))
        self.assertFalse(caps.uses_recursive_cte("select recursive_flag from t"))


if __name__ == "__main__":
    unittest.main()
