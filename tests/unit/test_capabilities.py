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


class TestProbeErrorsThatAreNotAnswers(unittest.TestCase):
    """A probe that fails for a reason other than SQL (connection lost, timeout) says nothing
    about the server, so it is raised and not cached as "unsupported"."""

    LOST = Exception(
        "<COMMUNICATION LINK ERROR> Failed to receive message; Details: Communication timed out"
    )

    def setUp(self):
        caps.clear_cache()

    def test_recursive_probe_raises_without_an_sqlcode(self):
        with self.assertRaises(Exception):
            caps.probe_recursive_cte(_Handle({"RECURSIVE": self.LOST}))

    def test_merge_probe_raises_without_an_sqlcode(self):
        with self.assertRaises(Exception):
            caps.probe_merge(_Handle({"MERGE": self.LOST}))

    def test_a_lost_connection_is_not_cached(self):
        key = ("h", 1972, "USER")
        with self.assertRaises(Exception):
            caps.supports(key, _Handle({"RECURSIVE": self.LOST}), "recursive_cte")
        self.assertTrue(caps.supports(key, _Handle({}), "recursive_cte"))


class TestServerVersionInTheMessage(unittest.TestCase):
    def setUp(self):
        caps.clear_cache()

    def test_parse_zversion(self):
        self.assertEqual(
            caps.parse_zversion(
                "IRIS for UNIX (Ubuntu Server LTS for ARM64 Containers) 2026.2 (Build 221U) Fri Jun 26 2026 09:59:12 EDT"
            ),
            "2026.2 (Build 221U)",
        )
        self.assertEqual(
            caps.parse_zversion(
                "IRIS for UNIX (Ubuntu Server LTS for x86-64) 2027.1.0RCTE (Build 100U) Wed Oct 21 2026"
            ),
            "2027.1.0RCTE (Build 100U)",
        )
        self.assertIsNone(caps.parse_zversion("something else"))

    def test_version_is_read_once_per_server(self):
        handle = _VersionHandle("IRIS for UNIX (x) 2026.2 (Build 221U) Fri")
        key = ("h", 1972, "USER")
        self.assertEqual(caps.server_version(key, handle), "2026.2 (Build 221U)")
        self.assertEqual(caps.server_version(key, handle), "2026.2 (Build 221U)")
        self.assertEqual(handle.queries, 1)

    def test_version_failure_gives_none(self):
        self.assertIsNone(
            caps.server_version(("h", 1, "U"), _Handle({"ZVERSION": Exception("lost")}))
        )

    def test_refusal_names_the_version_and_the_way_out(self):
        sql = "WITH RECURSIVE r(n) AS (select 1 union all select n+1 from r where n<3) select n from r"
        with self.assertRaises(DbtRuntimeError) as ctx:
            caps.check_statement(sql, lambda name: False, lambda: "2026.2 (Build 221U)")
        msg = str(ctx.exception)
        self.assertIn("IRIS 2026.2 (Build 221U)", msg)
        self.assertIn("Recursive CTEs", msg)
        self.assertIn("without recursion", msg)

    def test_refusal_without_a_version(self):
        sql = "WITH RECURSIVE r(n) AS (select 1) select n from r"
        with self.assertRaises(DbtRuntimeError) as ctx:
            caps.check_statement(sql, lambda name: False, lambda: None)
        self.assertIn("This IRIS server does not accept WITH RECURSIVE", str(ctx.exception))


class _VersionHandle:
    def __init__(self, zversion):
        self.zversion, self.queries = zversion, 0

    def cursor(self):
        handle = self

        class _C:
            def execute(self, sql, *a):
                handle.queries += 1

            def fetchone(self):
                return (handle.zversion,)

            def close(self):
                pass

        return _C()


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

    def test_comments_do_not_count(self):
        self.assertFalse(caps.uses_recursive_cte("-- with recursive is not used here\nselect 1"))
        self.assertFalse(caps.uses_recursive_cte("/* with recursive */ select 1"))
        self.assertFalse(caps.uses_recursive_cte("/* a\nwith recursive\nb */ select 1"))
        self.assertTrue(
            caps.uses_recursive_cte(
                '/* {"app": "dbt"} */ WITH RECURSIVE r(n) AS (select 1) select n from r'
            )
        )

    def test_comment_mention_never_asks(self):
        def ask(name):
            raise AssertionError("should not probe")

        caps.check_statement("-- WITH RECURSIVE would be nice\nselect 1", ask)

    def test_case_and_whitespace(self):
        self.assertTrue(caps.uses_recursive_cte("WITH\n  recursive r AS (select 1) select 1"))
        self.assertFalse(caps.uses_recursive_cte("select recursive_flag from t"))


if __name__ == "__main__":
    unittest.main()


class TestRelease(unittest.TestCase):
    def test_year_and_minor_from_the_parsed_version(self):
        from dbt.adapters.iris.capabilities import release

        self.assertEqual(release("2026.1 (Build 234U)"), (2026, 1))
        self.assertEqual(release("2026.3.0L (Build 196U)"), (2026, 3))
        self.assertEqual(release("2027.1.0RCTE.100.0 (Build 100U)"), (2027, 1))
        self.assertIsNone(release(None))
        self.assertIsNone(release("unknown"))
