import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


_frappe.throw = _throw
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.selling.sales_person_assignment import (  # noqa: E402
	assign_sales_person,
	expected_incentive,
	resolve_sales_person_for_user,
)


class _TeamRow(dict):
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError as exc:
			raise AttributeError(key) from exc

	def __setattr__(self, key, value):
		self[key] = value


class _SalesOrder:
	doctype = "Sales Order"

	def __init__(self, sales_team=None):
		self.sales_team = list(sales_team or [])

	def get(self, key, default=None):
		return getattr(self, key, default)

	def append(self, fieldname, values):
		assert fieldname == "sales_team"
		row = _TeamRow(values)
		self.sales_team.append(row)
		return row


class TestExpectedIncentive(unittest.TestCase):
	def test_amaranta_50000_at_1_percent(self):
		self.assertEqual(expected_incentive(50000, 100, 1), 500.0)

	def test_zero_rate(self):
		self.assertEqual(expected_incentive(50000, 100, 0), 0.0)


class TestAssignSalesPerson(unittest.TestCase):
	def test_skips_when_sales_team_exists(self):
		doc = _SalesOrder(sales_team=[_TeamRow(sales_person="Other", allocated_percentage=100)])
		with patch(
			"erpn_custom.selling.sales_person_assignment.resolve_sales_person_for_user"
		) as resolve:
			assign_sales_person(doc)
			resolve.assert_not_called()
		self.assertEqual(len(doc.sales_team), 1)
		self.assertEqual(doc.sales_team[0].sales_person, "Other")

	def test_assigns_when_empty(self):
		doc = _SalesOrder()
		with patch(
			"erpn_custom.selling.sales_person_assignment.resolve_sales_person_for_user",
			return_value={
				"employee": "HR-EMP-00002",
				"sales_person": "Amaranta Fernandez",
				"commission_rate": 1,
			},
		):
			assign_sales_person(doc)
		self.assertEqual(len(doc.sales_team), 1)
		row = doc.sales_team[0]
		self.assertEqual(row.sales_person, "Amaranta Fernandez")
		self.assertEqual(row.allocated_percentage, 100)
		self.assertEqual(row.commission_rate, 1.0)

	def test_idempotent_second_save(self):
		doc = _SalesOrder()
		resolved = {
			"employee": "HR-EMP-00002",
			"sales_person": "Amaranta Fernandez",
			"commission_rate": 1,
		}
		with patch(
			"erpn_custom.selling.sales_person_assignment.resolve_sales_person_for_user",
			return_value=resolved,
		):
			assign_sales_person(doc)
			assign_sales_person(doc)
		self.assertEqual(len(doc.sales_team), 1)

	def test_no_attribution_when_unresolved(self):
		doc = _SalesOrder()
		with patch(
			"erpn_custom.selling.sales_person_assignment.resolve_sales_person_for_user",
			return_value=None,
		):
			assign_sales_person(doc)
		self.assertEqual(doc.sales_team, [])


class TestResolveSalesPerson(unittest.TestCase):
	def test_guest_returns_none(self):
		self.assertIsNone(resolve_sales_person_for_user("Guest"))
		self.assertIsNone(resolve_sales_person_for_user(""))

	def test_no_employee_returns_none(self):
		with patch("erpn_custom.selling.sales_person_assignment.frappe.get_all", return_value=[]):
			self.assertIsNone(resolve_sales_person_for_user("admin@example.com"))

	def test_employee_without_sales_person_returns_none(self):
		def _get_all(doctype, **kwargs):
			if doctype == "Employee":
				return ["HR-EMP-00099"]
			return []

		with patch("erpn_custom.selling.sales_person_assignment.frappe.get_all", side_effect=_get_all):
			self.assertIsNone(resolve_sales_person_for_user("solo-employee@example.com"))

	def test_happy_path_amaranta(self):
		def _get_all(doctype, **kwargs):
			if doctype == "Employee":
				return ["HR-EMP-00002"]
			return [{"name": "Amaranta Fernandez", "commission_rate": 1}]

		with patch("erpn_custom.selling.sales_person_assignment.frappe.get_all", side_effect=_get_all):
			resolved = resolve_sales_person_for_user("amaranta@fragallardo.com")
		self.assertEqual(resolved["sales_person"], "Amaranta Fernandez")
		self.assertEqual(resolved["commission_rate"], 1.0)
		self.assertEqual(resolved["employee"], "HR-EMP-00002")

	def test_ambiguous_employee_throws(self):
		with patch(
			"erpn_custom.selling.sales_person_assignment.frappe.get_all",
			return_value=["E1", "E2"],
		):
			with self.assertRaises(_Throw):
				resolve_sales_person_for_user("dup@example.com")

	def test_ambiguous_sales_person_throws(self):
		def _get_all(doctype, **kwargs):
			if doctype == "Employee":
				return ["HR-EMP-00002"]
			return [
				{"name": "SP1", "commission_rate": 1},
				{"name": "SP2", "commission_rate": 2},
			]

		with patch("erpn_custom.selling.sales_person_assignment.frappe.get_all", side_effect=_get_all):
			with self.assertRaises(_Throw):
				resolve_sales_person_for_user("dup-sp@example.com")


if __name__ == "__main__":
	unittest.main()
