"""Expected recurrence behavior across downtime, revisions and canonical input."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/platform_sdk'))
from modular_platform.durable import QueueError
from modular_platform.recurrence import RecurrenceRule,cursor_after,occurrence_key,select


ANCHOR=datetime(2026,11,7,tzinfo=timezone.utc)
SCHEDULE='00000000-0000-4000-8000-000000000001'


class RecurrenceTests(unittest.TestCase):
    def setUp(self):self.rule=RecurrenceRule(ANCHOR,60,30,5)

    def test_never_selects_before_due_or_moves_the_future_cursor(self):
        selected=select(self.rule,ANCHOR,ANCHOR-timedelta(microseconds=1))
        self.assertIsNone(selected.nominal_at)
        self.assertEqual((selected.next_at,selected.skipped),(ANCHOR,0))

    def test_exact_due_and_expiry_boundaries(self):
        selected=select(self.rule,ANCHOR,ANCHOR)
        self.assertEqual((selected.nominal_at,selected.next_at,selected.skipped),(ANCHOR,ANCHOR+timedelta(seconds=60),0))
        self.assertEqual(select(self.rule,ANCHOR,ANCHOR+timedelta(seconds=29,microseconds=999999)).nominal_at,ANCHOR)
        expired=select(self.rule,ANCHOR,ANCHOR+timedelta(seconds=30))
        self.assertIsNone(expired.nominal_at)
        self.assertEqual(expired.skipped,1)

    def test_long_downtime_coalesces_only_latest_with_original_validity(self):
        now=ANCHOR+timedelta(days=200,seconds=10)
        selected=select(self.rule,ANCHOR,now)
        self.assertEqual(selected.nominal_at,ANCHOR+timedelta(days=200))
        self.assertEqual(selected.next_at,ANCHOR+timedelta(days=200,seconds=60))
        self.assertEqual(selected.skipped,200*24*60)

    def test_skip_late_cursor_advances_without_emitting_backlog(self):
        rule=replace(self.rule,missed='skip')
        self.assertEqual(select(rule,ANCHOR,ANCHOR+timedelta(seconds=5)).nominal_at,ANCHOR)
        selected=select(rule,ANCHOR,ANCHOR+timedelta(seconds=6))
        self.assertIsNone(selected.nominal_at)
        self.assertEqual((selected.next_at,selected.skipped),(ANCHOR+timedelta(seconds=60),1))
        selected=select(replace(rule,grace_seconds=1000),ANCHOR,ANCHOR+timedelta(seconds=60))
        self.assertIsNone(selected.nominal_at)
        self.assertEqual(selected.skipped,2)

    def test_resume_after_outstanding_job_uses_same_missed_policy(self):
        cursor=ANCHOR+timedelta(seconds=60)
        selected=select(self.rule,cursor,ANCHOR+timedelta(seconds=185))
        self.assertEqual((selected.nominal_at,selected.skipped),(ANCHOR+timedelta(seconds=180),2))

    def test_interval_edit_moves_strictly_past_considered_nominal(self):
        rule=replace(self.rule,interval_seconds=90)
        highwater=ANCHOR+timedelta(seconds=180)
        self.assertEqual(cursor_after(rule,highwater),ANCHOR+timedelta(seconds=270))
        self.assertEqual(cursor_after(rule,ANCHOR-timedelta(days=1)),ANCHOR)
        self.assertEqual(cursor_after(rule,highwater+timedelta(microseconds=1)),ANCHOR+timedelta(seconds=270))

    def test_occurrence_key_is_scope_stable_across_timezone_representation(self):
        alternate=ANCHOR.astimezone(timezone(timedelta(hours=3)))
        self.assertEqual(occurrence_key(SCHEDULE,ANCHOR),occurrence_key(SCHEDULE,alternate))
        self.assertNotEqual(occurrence_key(SCHEDULE,ANCHOR),occurrence_key(SCHEDULE,ANCHOR+timedelta(seconds=1)))
        self.assertLessEqual(len(occurrence_key(SCHEDULE,ANCHOR)),128)

    def test_wire_roundtrip_and_rejects_noncanonical_or_unknown_fields(self):
        wire=self.rule.wire()
        self.assertEqual(RecurrenceRule.from_wire(wire),self.rule)
        for bad in (dict(wire,protocol=True),dict(wire,extra=1),dict(wire,anchor_at='2026-11-07T03:00:00+03:00')):
            with self.assertRaises(QueueError):RecurrenceRule.from_wire(bad)

    def test_rejects_naive_subsecond_and_off_grid_instants(self):
        for bad in (ANCHOR.replace(tzinfo=None),ANCHOR+timedelta(microseconds=1)):
            with self.assertRaises(QueueError):replace(self.rule,anchor_at=bad)
        with self.assertRaises(QueueError):select(self.rule,ANCHOR+timedelta(seconds=1),ANCHOR)
        with self.assertRaises(QueueError):select(self.rule,ANCHOR,ANCHOR.replace(tzinfo=None))

    def test_resource_and_policy_bounds(self):
        for bad in (dict(interval_seconds=0),dict(interval_seconds=True),dict(validity_seconds=86401),
                    dict(attempt_seconds=3601),dict(validity_seconds=4),dict(grace_seconds=-1),dict(missed='catch_up'),dict(missed=[])):
            with self.assertRaises(QueueError):replace(self.rule,**bad)


if __name__=='__main__':unittest.main()
