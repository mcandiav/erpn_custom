import frappe
from frappe import _
from frappe.utils import flt


def assign_sales_person(doc, method=None):
	"""Default Sales Team from session user when the table is empty.

	Runs on Sales Order before_validate so ERPNext calculate_contribution
	sees the row in the same save.
	"""
	if getattr(doc, "doctype", None) != "Sales Order":
		return
	if doc.get("sales_team"):
		return

	resolved = resolve_sales_person_for_user(frappe.session.user)
	if not resolved:
		return

	row = doc.append(
		"sales_team",
		{
			"sales_person": resolved["sales_person"],
			"allocated_percentage": 100,
			"commission_rate": flt(resolved["commission_rate"]),
		},
	)
	return row


def resolve_sales_person_for_user(user):
	"""Map session user -> Employee -> Sales Person.

	Returns dict with sales_person + commission_rate, or None when the user
	is not a commercial seller. Raises on ambiguous matches.
	"""
	if not user or user == "Guest":
		return None

	employees = frappe.get_all(
		"Employee",
		filters={"user_id": user, "status": "Active"},
		pluck="name",
	)
	if not employees:
		return None
	if len(employees) > 1:
		frappe.throw(
			_("Multiple active Employees linked to user {0}. Fix Employee.user_id before saving Sales Order.").format(
				user
			)
		)

	employee = employees[0]
	persons = frappe.get_all(
		"Sales Person",
		filters={"employee": employee, "enabled": 1},
		fields=["name", "commission_rate"],
	)
	if not persons:
		return None
	if len(persons) > 1:
		frappe.throw(
			_("Multiple enabled Sales Persons linked to Employee {0}. Keep exactly one before saving Sales Order.").format(
				employee
			)
		)

	person = persons[0]
	return {
		"employee": employee,
		"sales_person": person["name"],
		"commission_rate": flt(person["commission_rate"]),
	}


def expected_incentive(net_amount, contribution_pct, commission_rate):
	"""Pure helper for tests: same formula ERPNext uses in calculate_contribution."""
	allocated = flt(net_amount) * flt(contribution_pct) / 100.0
	return flt(allocated * flt(commission_rate) / 100.0)
