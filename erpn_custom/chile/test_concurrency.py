import unittest
from datetime import datetime, timedelta

from erpn_custom.chile.concurrency import is_stale_run


class TestStaleRun(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 15, 12, 0, 0)
        self.ttl = 1800

    def test_finished_not_stale(self):
        self.assertFalse(is_stale_run("Success", self.now, self.now, self.now, self.ttl, "finished"))

    def test_running_active_job_not_stale(self):
        started = self.now - timedelta(minutes=5)
        self.assertFalse(is_stale_run("Running", started, started, self.now, self.ttl, "started"))

    def test_running_failed_job_stale(self):
        started = self.now - timedelta(minutes=1)
        self.assertTrue(is_stale_run("Running", started, started, self.now, self.ttl, "failed"))

    def test_running_past_ttl_stale(self):
        started = self.now - timedelta(seconds=1800)
        self.assertTrue(is_stale_run("Running", started, started, self.now, self.ttl, "started"))

    def test_queued_missing_job_within_grace_not_stale(self):
        created = self.now - timedelta(seconds=30)
        self.assertFalse(is_stale_run("Queued", None, created, self.now, self.ttl, None))

    def test_queued_missing_job_after_grace_stale(self):
        created = self.now - timedelta(seconds=120)
        self.assertTrue(is_stale_run("Queued", None, created, self.now, self.ttl, None))

    def test_queued_rq_job_not_stale(self):
        created = self.now - timedelta(seconds=30)
        self.assertFalse(is_stale_run("Queued", None, created, self.now, self.ttl, "queued"))
