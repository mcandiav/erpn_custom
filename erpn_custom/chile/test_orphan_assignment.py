import unittest

from erpn_custom.chile.orphan_rules import (
	MANUAL_REASON,
	MANUAL_RULE,
	assignment_conflict,
	orphan_eligibility,
)


class TestOrphanEligibility(unittest.TestCase):
	def test_orphan_ok(self):
		ok, reason = orphan_eligibility(
			{"deposit": 119990, "withdrawal": 0, "docstatus": 0, "party": ""}
		)
		self.assertTrue(ok)
		self.assertEqual(reason, "")

	def test_with_party_not_orphan(self):
		ok, reason = orphan_eligibility(
			{
				"deposit": 119990,
				"withdrawal": 0,
				"docstatus": 1,
				"party": "Cynthia Contreras Soto",
			}
		)
		self.assertFalse(ok)
		self.assertEqual(reason, "already_assigned")

	def test_cancelled(self):
		ok, reason = orphan_eligibility(
			{"deposit": 119990, "withdrawal": 0, "docstatus": 2, "party": ""}
		)
		self.assertFalse(ok)
		self.assertEqual(reason, "cancelled")

	def test_not_credit(self):
		ok, reason = orphan_eligibility(
			{"deposit": 0, "withdrawal": 100, "docstatus": 1, "party": ""}
		)
		self.assertFalse(ok)
		self.assertEqual(reason, "not_credit")


class TestAssignmentConflict(unittest.TestCase):
	def test_same_customer_no_conflict(self):
		self.assertFalse(assignment_conflict("Cynthia Contreras Soto", "Cynthia Contreras Soto"))

	def test_other_customer_conflict(self):
		self.assertTrue(assignment_conflict("Otro Cliente", "Cynthia Contreras Soto"))

	def test_empty_party_no_conflict(self):
		self.assertFalse(assignment_conflict("", "Cynthia Contreras Soto"))
		self.assertFalse(assignment_conflict(None, "Cynthia Contreras Soto"))


class TestManualConstants(unittest.TestCase):
	def test_rule_differs_from_exact_tax_id(self):
		self.assertEqual(MANUAL_RULE, "manual-attribution-v1")
		self.assertNotEqual(MANUAL_RULE, "Exact Tax ID")
		self.assertIn("manual", MANUAL_REASON.lower())


if __name__ == "__main__":
	unittest.main()
