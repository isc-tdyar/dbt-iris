"""IRIS reads a number in GROUP BY as a constant, not a column position (documented in the IRIS
SQL reference): GROUP BY 1 puts every row in one group, and next to named columns the number is
ignored. Other warehouses read it as the first select-list column, so the adapter refuses it."""
import unittest

from dbt_common.exceptions import DbtRuntimeError

from dbt.adapters.iris import group_by_numbers as g


class TestNumbersInGroupBy(unittest.TestCase):
    def test_finds_numbers(self):
        self.assertEqual(g.numbers("select a, count(*) from t group by 1"), ["1"])
        self.assertEqual(
            g.numbers("select a, b, count(*) from t group by 1, 2 order by 1"), ["1", "2"]
        )
        self.assertEqual(
            g.numbers("select a, c, count(*) from t GROUP  BY 1, c having count(*) > 1"), ["1"]
        )

    def test_in_subqueries_and_ctes(self):
        sql = "with x as (select a, count(*) n from t group by 1) select * from (select a from x group by 1) s"
        self.assertEqual(g.numbers(sql), ["1", "1"])

    def test_named_columns_and_expressions_are_fine(self):
        for sql in (
            "select a, count(*) from t group by a",
            "select a + 1, count(*) from t group by a + 1",
            "select substring(a, 1, 2), count(*) from t group by substring(a, 1, 2)",
            "select a from t order by 1",
            "select a, count(*) from t group by a order by 1 limit 1",
            "select a from t where b in (1, 2) group by a",
            "select %exact(a), count(*) from t group by %exact(a)",
        ):
            self.assertEqual(g.numbers(sql), [], sql)

    def test_strings_comments_and_names_are_ignored(self):
        sql = "select 'group by 1' as s, \"group by 1\" from t -- group by 1\n/* group by 2 */ group by s"
        self.assertEqual(g.numbers(sql), [])

    def test_partition_by_and_window_order_are_not_group_by(self):
        sql = "select a, row_number() over (partition by 1 order by 1) from t group by a"
        self.assertEqual(g.numbers(sql), [])


class TestCheck(unittest.TestCase):
    def test_refuses_with_the_fix(self):
        with self.assertRaises(DbtRuntimeError) as e:
            g.check("create table s.t as select status, count(*) as n from orders group by 1")
        msg = str(e.exception)
        self.assertIn("GROUP BY 1", msg)
        self.assertIn("constant", msg)
        self.assertIn("one group", msg)
        self.assertIn("Name the columns", msg)

    def test_lists_every_number(self):
        with self.assertRaises(DbtRuntimeError) as e:
            g.check("select a, b, count(*) from t group by 1, 2")
        self.assertIn("GROUP BY 1, 2", str(e.exception))

    def test_passes_named_columns(self):
        g.check("select a, count(*) from t group by a")


if __name__ == "__main__":
    unittest.main()
