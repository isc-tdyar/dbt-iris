"""A UNION whose branches give one column a DATE or TIME in one branch and another type in the
other makes IRIS store wrong values when it builds a table from it ('66154' for 2022-02-14). The
adapter reads each branch's column types with a zero-row query and refuses the statement first."""
import unittest

from dbt_common.exceptions import DbtRuntimeError

from dbt.adapters.iris import union_types as ut

DATE, TIME, TIMESTAMP, VARCHAR, INTEGER = 9, 10, 11, 12, 4


def col(name, code, precision=20, nullable=1):
    return (name, code, None, None, precision, 0, nullable)


NULL = ("d", VARCHAR, None, None, 1, 0, 1)  # what IRIS reports for a bare NULL


class TestTargetBody(unittest.TestCase):
    def test_create_table_as(self):
        sql = '/* {"app": "dbt"} */\n  create table "s"."t" as\n select 1 as a'
        self.assertEqual(ut.target_body(sql).strip(), "select 1 as a")

    def test_global_temporary_table(self):
        sql = 'create global temporary table "s"."t__dbt_tmp" as with x as (select 1 a) select a from x'
        self.assertEqual(ut.target_body(sql).strip(), "with x as (select 1 a) select a from x")

    def test_insert_select(self):
        sql = 'insert into "s"."t" ("a", "b") select a, b from x union all select a, b from y'
        self.assertTrue(ut.target_body(sql).strip().startswith("select a, b from x"))

    def test_other_statements_have_no_body(self):
        for sql in ("select 1 union all select 2", "insert into t values (1)", "drop table t"):
            self.assertIsNone(ut.target_body(sql), sql)


class TestUnionGroups(unittest.TestCase):
    def test_no_union(self):
        self.assertEqual(ut.union_groups("select a from t"), ("", []))

    def test_top_level_branches(self):
        prefix, groups = ut.union_groups(
            "select a from t union all select b from u union select c from v"
        )
        self.assertEqual(prefix, "")
        self.assertEqual(groups, [["select a from t", "select b from u", "select c from v"]])

    def test_trailing_order_by_is_left_out(self):
        _, groups = ut.union_groups("select a from t union all select b from u order by 1")
        self.assertEqual(groups, [["select a from t", "select b from u"]])

    def test_union_inside_a_cte_keeps_the_with_prefix(self):
        sql = "with x as (select a from t union all select b from u), y as (select 1 z) select * from x"
        prefix, groups = ut.union_groups(sql)
        self.assertTrue(prefix.startswith("with x as ("), prefix)
        self.assertTrue(prefix.rstrip().endswith("(select 1 z)"), prefix)
        self.assertEqual(groups, [["select a from t", "select b from u"]])

    def test_union_inside_a_subquery(self):
        _, groups = ut.union_groups(
            "select d from (select a as d from t union all select b from u) s"
        )
        self.assertEqual(groups, [["select a as d from t", "select b from u"]])

    def test_union_words_in_strings_comments_and_names_are_ignored(self):
        sql = (
            "select 'union all' as u, \"union\" from t -- union all\n/* union */ where reunion = 1"
        )
        self.assertEqual(ut.union_groups(sql), ("", []))

    def test_parenthesised_branches(self):
        _, groups = ut.union_groups("(select a from t) union all (select b from u)")
        self.assertEqual(groups, [["(select a from t)", "(select b from u)"]])


class TestMismatches(unittest.TestCase):
    def test_date_and_text(self):
        found = ut.mismatches([[col("d", DATE)], [col("d", VARCHAR, 4096, 2)]])
        self.assertEqual(found, [("d", ["DATE", "VARCHAR"])])

    def test_time_and_text(self):
        found = ut.mismatches([[col("t", VARCHAR)], [col("t", TIME)]])
        self.assertEqual(found, [("t", ["TIME", "VARCHAR"])])

    def test_date_and_time(self):
        self.assertEqual(
            ut.mismatches([[col("d", DATE)], [col("d", TIME)]]), [("d", ["DATE", "TIME"])]
        )

    def test_date_and_integer(self):
        self.assertEqual(
            ut.mismatches([[col("d", DATE)], [col("d", INTEGER)]]), [("d", ["DATE", "INTEGER"])]
        )

    def test_safe_combinations(self):
        for branches in (
            [[col("d", DATE)], [col("d", DATE)]],
            [[col("d", DATE)], [col("d", TIMESTAMP)]],
            [[col("d", TIMESTAMP)], [col("d", VARCHAR)]],
            [[col("d", VARCHAR)], [col("d", INTEGER)]],
            [[col("d", DATE)], [NULL]],
            [[NULL], [col("d", TIME)]],
        ):
            self.assertEqual(ut.mismatches(branches), [], branches)

    def test_columns_are_matched_by_position_and_named_from_the_first_branch(self):
        found = ut.mismatches(
            [[col("id", INTEGER), col("visited", DATE)], [col("x", INTEGER), col("y", VARCHAR)]]
        )
        self.assertEqual(found, [("visited", ["DATE", "VARCHAR"])])

    def test_branches_with_different_column_counts_are_not_judged(self):
        self.assertEqual(
            ut.mismatches([[col("d", DATE)], [col("d", VARCHAR), col("e", DATE)]]), []
        )


class TestCheck(unittest.TestCase):
    SQL = (
        'create table "s"."visits" as select cast(\'2022-02-14\' as date) as visited '
        "union all select '2022-02-15'"
    )

    def _describe(self, by_branch):
        asked = []

        def describe(query):
            asked.append(query)
            for needle, description in by_branch.items():
                if needle in query:
                    return description
            return None

        return describe, asked

    def test_refuses_with_a_message_naming_the_column_the_damage_and_the_fix(self):
        describe, asked = self._describe(
            {"as date": [col("visited", DATE)], "'2022-02-15'": [col("visited", VARCHAR, 4096, 2)]}
        )
        with self.assertRaises(DbtRuntimeError) as e:
            ut.check(self.SQL, describe)
        msg = str(e.exception)
        self.assertIn("Column 'visited' is DATE in one UNION branch and VARCHAR in another", msg)
        self.assertIn("internal day numbers (for example '66154' for 2022-02-14)", msg)
        self.assertIn("cast('2022-02-15' as date)", msg)
        self.assertNotIn("TIME", msg)
        self.assertTrue(all(q.rstrip().endswith("where 1=0") for q in asked), asked)

    def test_a_branch_that_cannot_be_described_skips_the_check(self):
        describe, _ = self._describe({"as date": [col("visited", DATE)]})
        ut.check(self.SQL, describe)

    def test_statements_without_union_are_not_probed(self):
        describe, asked = self._describe({})
        ut.check('create table "s"."t" as select 1 as a', describe)
        ut.check("select 1 union all select 2", describe)
        self.assertEqual(asked, [])

    def test_a_time_column_is_described_as_seconds(self):
        msg = ut.message([("at_time", ["TIME", "VARCHAR"])])
        self.assertIn("Column 'at_time' is TIME in one UNION branch and VARCHAR in another", msg)
        self.assertIn("seconds since midnight (for example '36672' for 10:11:12)", msg)

    def test_the_with_prefix_is_sent_with_each_branch(self):
        sql = (
            'create table "s"."t" as with base as (select 1 a) '
            "select a from base union all select a from base"
        )
        describe, asked = self._describe({"from base": [col("a", INTEGER)]})
        ut.check(sql, describe)
        self.assertEqual(len(asked), 2)
        self.assertTrue(all(q.startswith("with base as (select 1 a)") for q in asked), asked)


if __name__ == "__main__":
    unittest.main()
