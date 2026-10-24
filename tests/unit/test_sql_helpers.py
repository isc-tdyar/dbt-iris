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
        self.executed = getattr(self, "executed", []) + [sql]

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


class TestRunSqlForTestsSplitsScripts(unittest.TestCase):
    """dbt's test suites send setup scripts with several statements; IRIS runs one per call."""

    def test_split_statements(self):
        from dbt.adapters.iris.impl import split_statements

        self.assertEqual(
            split_statements("create table a (x int);\n insert into a select 1 ;  "),
            ["create table a (x int)", "insert into a select 1"],
        )
        self.assertEqual(
            split_statements("select 'a;b' as v; select 2"), ["select 'a;b' as v", "select 2"]
        )
        self.assertEqual(split_statements("-- one; two\nselect 1"), ["-- one; two\nselect 1"])
        self.assertEqual(split_statements("/* a; b */ select 1"), ["/* a; b */ select 1"])
        self.assertEqual(split_statements("select 1"), ["select 1"])

    def test_each_statement_runs_and_the_last_one_is_fetched(self):
        conn = _Conn([(1,)])
        rows = IRISAdapter.run_sql_for_tests(
            None, "create table a (x int); select x from a", "all", conn
        )
        self.assertEqual(conn.handle.cur.executed, ["create table a (x int)", "select x from a"])
        self.assertEqual(rows, [(1,)])


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


class TestRowsDifferentSql(unittest.TestCase):
    """check_relations_equal compares two relations with this SQL. On IRIS a bare EXCEPT
    compares strings under SQLUPPER ('Female' = 'FEMALE', 'x' = 'x '), never matches a stream
    (TEXT / LONGVARCHAR) column to anything, and compares a DATE with a VARCHAR by the DATE's
    internal value. Each column is normalised by its own type on each side before EXCEPT."""

    @staticmethod
    def _adapter(types_a, types_b):
        from types import SimpleNamespace
        from unittest import mock

        def cols(types):
            return [SimpleNamespace(name=n, dtype=t) for n, t in types.items()]

        adapter = mock.Mock()
        adapter.quote = lambda name: f'"{name}"'
        by_rel = {"A": cols(types_a), "B": cols(types_b)}
        adapter.get_columns_in_relation = lambda rel: by_rel[rel]
        return adapter

    def _sql(self, types_a, types_b, names=None):
        adapter = self._adapter(types_a, types_b)
        return IRISAdapter.get_rows_different_sql(adapter, "A", "B", names or list(types_a))

    def test_counts_both_directions_with_except(self):
        sql = self._sql({"id": "integer", "v": "varchar"}, {"id": "integer", "v": "varchar"})
        self.assertNotEqual(sql.strip().upper(), "SELECT 0,0")
        self.assertEqual(sql.upper().count("EXCEPT"), 2)
        head = "select (select count(*) from A) - (select count(*) from B), "
        self.assertTrue(sql.startswith(head), sql)

    def test_strings_compare_exactly(self):
        sql = self._sql({"v": "varchar"}, {"v": "char"})
        self.assertEqual(sql.count('%EXACT("v")'), 4)

    def test_stream_compares_by_content(self):
        sql = self._sql({"g": "longvarchar"}, {"g": "varchar"})
        self.assertIn('select %EXACT(SUBSTRING("g", 1, 3641144)) from A EXCEPT', sql)
        self.assertIn('select %EXACT("g") from B', sql)

    def test_temporal_compares_as_odbc_text(self):
        sql = self._sql({"d": "date", "t": "timestamp"}, {"d": "varchar", "t": "timestamp"})
        self.assertIn(
            '%EXACT(CAST("d" AS VARCHAR(64))), %EXACT(CAST("t" AS VARCHAR(64))) from A', sql
        )
        self.assertIn('%EXACT("d"), %EXACT(CAST("t" AS VARCHAR(64))) from B', sql)

    def test_numbers_and_unknown_columns_are_left_bare(self):
        types_a, types_b = {"n": "numeric", "x": "bigint"}, {"n": "double", "x": "bigint"}
        sql = self._sql(types_a, types_b, ["n", "x", "missing"])
        self.assertIn('select "n", "x", "missing" from A', sql)
        self.assertIn('select "n", "x", "missing" from B', sql)

    def test_column_names_match_types_case_insensitively(self):
        sql = self._sql({"State": "varchar"}, {"STATE": "varchar"}, ["state"])
        self.assertEqual(sql.count('%EXACT("state")'), 4)

    def test_no_column_names_uses_relation_a_columns(self):
        adapter = self._adapter(
            {"id": "integer", "v": "varchar"}, {"id": "integer", "v": "varchar"}
        )
        sql = IRISAdapter.get_rows_different_sql(adapter, "A", "B")
        self.assertIn('select "id", %EXACT("v") from A', sql)
