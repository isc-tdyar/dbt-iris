"""IRIS SQL cannot place a WITH clause inside a derived table:
``select ... from ( with x as (...) select ... ) t`` is rejected. dbt wraps
model SQL that way for tests. The adapter hoists leading CTEs above the
wrapper instead. Also: rows returned to dbt's test utilities must not be live
cursor proxies."""
import unittest

from dbt.adapters.iris.impl import split_leading_ctes, flatten_nested_ctes, IRISAdapter


class TestSplitLeadingCtes(unittest.TestCase):
    def test_no_cte_returns_empty_prefix(self):
        prefix, body = split_leading_ctes("select 1 as a")
        self.assertEqual(prefix, "")
        self.assertEqual(body.strip(), "select 1 as a")

    def test_single_cte(self):
        sql = "with x as (select 1 as a) select a from x"
        prefix, body = split_leading_ctes(sql)
        self.assertEqual(prefix.strip(), "with x as (select 1 as a)")
        self.assertEqual(body.strip(), "select a from x")

    def test_multiple_ctes_with_nested_parens_and_newlines(self):
        sql = """with __dbt__cte__a as (
  select id from t where f(id, (1+2)) > 0
), b as (
  select a.id from __dbt__cte__a a join t on (t.id = a.id)
)
select * from b"""
        prefix, body = split_leading_ctes(sql)
        self.assertTrue(prefix.strip().startswith("with __dbt__cte__a as ("))
        self.assertTrue(prefix.strip().endswith(")"))
        self.assertEqual(body.strip(), "select * from b")

    def test_cte_with_column_list_and_recursive(self):
        sql = (
            "with recursive tree(id, d) as (select 1, 0 union all select 2, 1) select * from tree"
        )
        prefix, body = split_leading_ctes(sql)
        self.assertTrue(prefix.lower().startswith("with recursive tree(id, d) as ("))
        self.assertEqual(body.strip(), "select * from tree")

    def test_leading_comment_and_whitespace(self):
        sql = "\n  -- header\n  WITH x AS (select 1 as a)\n  SELECT a FROM x"
        prefix, body = split_leading_ctes(sql)
        self.assertIn("WITH x AS", prefix)
        self.assertEqual(body.strip(), "SELECT a FROM x")

    def test_string_literal_containing_parens_and_with(self):
        sql = "with x as (select ') with (' as s) select s from x"
        prefix, body = split_leading_ctes(sql)
        self.assertEqual(body.strip(), "select s from x")


class _LiveRow:
    def __init__(self, cursor, values):
        self._c, self._v = cursor, values

    def __iter__(self):
        if self._c.closed:
            raise RuntimeError("Cursor closed")
        return iter(self._v)


class _Cur:
    def __init__(self, rows):
        self.closed = False
        self._rows = [_LiveRow(self, r) for r in rows]

    def execute(self, sql):
        pass

    def fetchone(self):
        return self._rows[0]

    def fetchall(self):
        return self._rows

    def close(self):
        self.closed = True


class _Handle:
    closed = False

    def __init__(self, rows):
        self.cur = _Cur(rows)

    def cursor(self):
        return self.cur

    def commit(self):
        pass

    def rollback(self):
        pass


class _Conn:
    def __init__(self, rows):
        self.handle = _Handle(rows)
        self.transaction_open = True


class TestRunSqlForTestsDetaches(unittest.TestCase):
    def test_fetch_one_survives_close(self):
        conn = _Conn([(10, "x")])
        row = IRISAdapter.run_sql_for_tests(None, "select 1", "one", conn)
        conn.handle.cur.close()
        self.assertEqual(tuple(row), (10, "x"))

    def test_fetch_all_survives_close(self):
        conn = _Conn([(1, "a"), (2, "b")])
        rows = IRISAdapter.run_sql_for_tests(None, "select 1", "all", conn)
        conn.handle.cur.close()
        self.assertEqual([tuple(r) for r in rows], [(1, "a"), (2, "b")])


class TestFlattenNestedCtes(unittest.TestCase):
    """dbt injects an ephemeral model as a CTE; if that model itself starts
    with WITH, the result is a WITH nested inside a CTE body. IRIS's SQL server
    fails to compile that. Hoist the inner CTEs into the outer list, before the
    CTE that used them, preserving order."""

    def test_no_nesting_unchanged(self):
        sql = "with a as (select 1 as x) select x from a"
        self.assertEqual(flatten_nested_ctes(sql), sql)

    def test_inner_ctes_hoisted_before_their_owner(self):
        sql = (
            "with e as ( with inner1 as (select id from t) select id from inner1 where id is not null ), "
            "o as (select id from e where id < 10) select count(*) from o"
        )
        out = flatten_nested_ctes(sql)
        self.assertNotIn("as ( with", out.replace("\n", " ").lower())
        i_inner, i_e, i_o = out.find("inner1 as ("), out.find("e as ("), out.find("o as (")
        self.assertTrue(0 < i_inner < i_e < i_o)
        self.assertTrue(out.rstrip().endswith("select count(*) from o"))

    def test_two_levels(self):
        sql = "with a as (with b as (with c as (select 1 as x) select x from c) select x from b) select x from a"
        out = flatten_nested_ctes(sql)
        self.assertNotIn("(with", out.replace(" ", "").lower())
        self.assertLess(out.find("c as ("), out.find("b as ("))
        self.assertLess(out.find("b as ("), out.find("a as ("))

    def test_non_cte_sql_unchanged(self):
        sql = "select * from t where x in (select y from u)"
        self.assertEqual(flatten_nested_ctes(sql), sql)

    def test_dbt_ephemeral_shape(self):
        sql = """with  __dbt__cte__ephemeral as (
with my_cool_cte as (
  select name, id from "s"."base"
)
select id, name from my_cool_cte where id is not null
), my_other_cool_cte as (
    select id, name from __dbt__cte__ephemeral
    where id < 1000
)
select name, id from my_other_cool_cte"""
        out = flatten_nested_ctes(sql)
        low = out.lower()
        self.assertLess(low.find("my_cool_cte as ("), low.find("__dbt__cte__ephemeral as ("))
        self.assertNotIn("as (\nwith", low)
        self.assertTrue(out.rstrip().endswith("select name, id from my_other_cool_cte"))


class TestFlattenKeepsRecursive(unittest.TestCase):
    """An ephemeral model that is a recursive CTE, injected into its parent (spec 18 FR-16)."""

    def test_inner_recursive_makes_the_outer_with_recursive(self):
        from dbt.adapters.iris.impl import flatten_nested_ctes

        sql = (
            "with __dbt__cte__counter as (\nWITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 3) "
            "SELECT n FROM r\n) select n from __dbt__cte__counter where n > 1"
        )
        out = flatten_nested_ctes(sql)
        self.assertTrue(out.lower().startswith("with recursive "), out)
        self.assertIn("__dbt__cte__counter as (SELECT n FROM r)", out)
