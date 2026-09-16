import unittest

from erpn_custom.chile.realize_rules import (
	allocation_plan,
	is_eligible_credit,
	proposed_apply_amount,
	sql_savepoint_name,
)


class TestRealizeEligibility(unittest.TestCase):
	def test_credit_with_customer(self):
		ok, reason = is_eligible_credit(
			{
				"deposit": 119990,
				"withdrawal": 0,
				"docstatus": 1,
				"party_type": "Customer",
				"party": "Cynthia Contreras Soto",
			}
		)
		self.assertTrue(ok)
		self.assertEqual(reason, "")

	def test_debit_skipped(self):
		ok, reason = is_eligible_credit(
			{
				"deposit": 0,
				"withdrawal": 5000,
				"docstatus": 1,
				"party_type": "Customer",
				"party": "Cynthia Contreras Soto",
			}
		)
		self.assertFalse(ok)
		self.assertEqual(reason, "not_credit")

	def test_unattributed_skipped(self):
		ok, reason = is_eligible_credit(
			{
				"deposit": 119990,
				"withdrawal": 0,
				"docstatus": 1,
				"party_type": "",
				"party": "",
			}
		)
		self.assertFalse(ok)
		self.assertEqual(reason, "no_customer")

	def test_cancelled_skipped(self):
		ok, reason = is_eligible_credit(
			{
				"deposit": 119990,
				"withdrawal": 0,
				"docstatus": 2,
				"party_type": "Customer",
				"party": "Cynthia Contreras Soto",
			}
		)
		self.assertFalse(ok)
		self.assertEqual(reason, "cancelled")


class TestAllocationPlan(unittest.TestCase):
	def test_cynthia_acceptance(self):
		self.assertEqual(proposed_apply_amount(119990, 50000), 50000)
		plan, leftover = allocation_plan(
			[{"name": "PE-CYNTHIA", "unallocated_amount": 119990}],
			50000,
		)
		self.assertEqual(leftover, 0)
		self.assertEqual(plan, [{"name": "PE-CYNTHIA", "amount": 50000}])

	def test_split_500_then_300_then_200(self):
		payments = [{"name": "PE-500", "unallocated_amount": 500}]
		first, leftover = allocation_plan(payments, 300)
		self.assertEqual(first, [{"name": "PE-500", "amount": 300}])
		self.assertEqual(leftover, 0)
		payments[0]["unallocated_amount"] = 200
		second, leftover = allocation_plan(payments, 200)
		self.assertEqual(second, [{"name": "PE-500", "amount": 200}])
		self.assertEqual(leftover, 0)

	def test_reject_over_available(self):
		self.assertEqual(proposed_apply_amount(15000, 10000), 10000)
		plan, leftover = allocation_plan(
			[{"name": "PE-15", "unallocated_amount": 15000}],
			16000,
		)
		self.assertEqual(plan, [{"name": "PE-15", "amount": 15000}])
		self.assertEqual(leftover, 1000)

	def test_savepoint_strips_hyphens(self):
		savepoint = sql_savepoint_name("realize", "ACC-BTN-2026-00854")
		self.assertNotIn("-", savepoint)
		self.assertTrue(savepoint.startswith("realize_"))

	def test_fifo_across_two_payments(self):
		plan, leftover = allocation_plan(
			[
				{"name": "PE-A", "unallocated_amount": 40000},
				{"name": "PE-B", "unallocated_amount": 80000},
			],
			50000,
		)
		self.assertEqual(
			plan,
			[
				{"name": "PE-A", "amount": 40000},
				{"name": "PE-B", "amount": 10000},
			],
		)
		self.assertEqual(leftover, 0)


if __name__ == "__main__":
	unittest.main()
