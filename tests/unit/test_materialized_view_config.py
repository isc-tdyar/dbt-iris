"""materialized_view models: the iris_materialized_view_as setting (table or view, default table),
its validation, and the once-per-run warning that lists the models left on the default."""
import threading
import unittest

from dbt_common.exceptions import CompilationError

from dbt.adapters.iris import materialized_view as mv


def _node(uid, materialized="materialized_view", **config):
    return {
        "unique_id": uid,
        "name": uid.split(".")[-1],
        "config": {"materialized": materialized, **config},
    }


class TestResolveMode(unittest.TestCase):
    def test_unset_is_table(self):
        self.assertEqual(mv.resolve_mode(None), "table")

    def test_table_and_view_are_accepted(self):
        self.assertEqual(mv.resolve_mode("table"), "table")
        self.assertEqual(mv.resolve_mode("view"), "view")

    def test_case_and_spaces_are_ignored(self):
        self.assertEqual(mv.resolve_mode(" View "), "view")

    def test_other_values_fail_listing_the_allowed_ones(self):
        for bad in ("incremental", "matview", "", 1):
            with self.assertRaises(CompilationError) as e:
                mv.resolve_mode(bad)
            msg = str(e.exception)
            self.assertIn("iris_materialized_view_as", msg)
            self.assertIn("'table'", msg)
            self.assertIn("'view'", msg)


class TestModelsOnTheDefault(unittest.TestCase):
    def test_lists_selected_materialized_view_models_without_the_setting(self):
        nodes = {
            "model.p.a": _node("model.p.a"),
            "model.p.b": _node("model.p.b", iris_materialized_view_as="table"),
            "model.p.c": _node("model.p.c", iris_materialized_view_as="view"),
            "model.p.d": _node("model.p.d", materialized="table"),
            "model.p.e": _node("model.p.e"),
            "model.p.f": _node("model.p.f"),
        }
        selected = ["model.p.a", "model.p.b", "model.p.c", "model.p.d", "model.p.e"]
        self.assertEqual(mv.models_on_default(nodes, selected), ["a", "e"])

    def test_no_selection_means_every_node(self):
        nodes = {"model.p.z": _node("model.p.z"), "model.p.y": _node("model.p.y")}
        self.assertEqual(mv.models_on_default(nodes, None), ["y", "z"])


class TestWarning(unittest.TestCase):
    def test_text_names_the_models_and_both_ways_out(self):
        text = mv.warning_text(["orders_mv", "daily_mv"])
        self.assertIn("IRIS has no materialized views", text)
        self.assertIn("orders_mv, daily_mv", text)
        self.assertIn("incremental", text)
        self.assertIn("iris_materialized_view_as: view", text)

    def test_once_per_key_even_across_threads(self):
        key = object()
        hits = []
        barrier = threading.Barrier(8)

        def go():
            barrier.wait()
            hits.append(mv.first_time(key))

        threads = [threading.Thread(target=go) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(hits.count(True), 1)
        self.assertTrue(mv.first_time(object()))


if __name__ == "__main__":
    unittest.main()
