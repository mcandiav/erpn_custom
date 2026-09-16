import json
import unittest

from erpn_custom.chile.attempt import conflict_reason, serialize_candidates


class TestAttemptPayload(unittest.TestCase):
    def test_serialize_unique_order(self):
        count, payload = serialize_candidates(["A", "B", "A"])
        self.assertEqual(count, 2)
        self.assertEqual(json.loads(payload), ["A", "B"])

    def test_one_conflict_row_reason(self):
        reason = conflict_reason("12345678-K", ["C1", "C2", "C3"])
        self.assertEqual(reason, "3 Customers coinciden con RUT 12345678-K")

    def test_empty_candidates(self):
        count, payload = serialize_candidates([])
        self.assertEqual(count, 0)
        self.assertEqual(json.loads(payload), [])
