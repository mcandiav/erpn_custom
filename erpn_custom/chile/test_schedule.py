import unittest
from datetime import datetime, timedelta

from erpn_custom.chile.schedule import interval_due, parse_datetime


class TestSchedule(unittest.TestCase):
    def test_due_when_never_ran(self):
        now = datetime(2026, 9, 15, 12, 0, 0)
        self.assertTrue(interval_due(None, 15, now))

    def test_not_due_inside_interval(self):
        now = datetime(2026, 9, 15, 12, 10, 0)
        last = datetime(2026, 9, 15, 12, 0, 0)
        self.assertFalse(interval_due(last, 15, now))

    def test_due_after_interval(self):
        now = datetime(2026, 9, 15, 12, 15, 0)
        last = datetime(2026, 9, 15, 12, 0, 0)
        self.assertTrue(interval_due(last, 15, now))

    def test_minimum_one_minute(self):
        now = datetime(2026, 9, 15, 12, 1, 0)
        last = datetime(2026, 9, 15, 12, 0, 0)
        self.assertTrue(interval_due(last, 0, now))

    def test_parse_frappe_string(self):
        parsed = parse_datetime("2026-09-15 12:00:00")
        self.assertEqual(parsed, datetime(2026, 9, 15, 12, 0, 0))
        later = parsed + timedelta(minutes=15)
        self.assertTrue(interval_due("2026-09-15 12:00:00", 15, later))
