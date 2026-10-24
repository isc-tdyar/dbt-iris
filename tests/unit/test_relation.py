"""Event-time filters for microbatch inputs (spec 18 FR-11).

dbt's default renders the batch bounds as strings with a timezone offset
('2020-01-01 00:00:00+00:00'), which an IRIS TIMESTAMP comparison does not match.
"""
import datetime as dt
import unittest

from dbt.adapters.base.relation import EventTimeFilter

from dbt.adapters.iris.relation import IRISRelation

UTC = dt.timezone.utc


class TestEventTimeFilter(unittest.TestCase):
    def _render(self, start=None, end=None):
        rel = IRISRelation.create(schema="s", identifier="t")
        return rel._render_event_time_filtered(
            EventTimeFilter(field_name="event_time", start=start, end=end)
        )

    def test_both_bounds(self):
        out = self._render(
            dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 2, tzinfo=UTC)
        )
        self.assertEqual(
            out,
            "event_time >= cast('2020-01-01 00:00:00' as timestamp) and "
            "event_time < cast('2020-01-02 00:00:00' as timestamp)",
        )

    def test_start_only(self):
        self.assertEqual(
            self._render(dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC)),
            "event_time >= cast('2020-01-01 06:30:00' as timestamp)",
        )

    def test_none(self):
        self.assertEqual(self._render(), "")


class TestScratchRelationNames(unittest.TestCase):
    """Temporary, intermediate and backup tables carry the invocation id, so two dbt runs at
    once never share one (spec 18 FR-17, issue #3)."""

    def test_backup_relation_uses_the_invocation_suffix(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2] / "dbt/include/iris/macros/adapters/relation.sql"
        ).read_text()
        start = text.index("macro iris__make_backup_relation")
        body = text[start : text.index("endmacro", start)]
        self.assertIn("iris__suffix()", body)
        self.assertIn("__dbt_backup", body)
