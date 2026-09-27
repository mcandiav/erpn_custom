import frappe

from erpn_custom.encargo.known_item import known_item_values


def execute():
	rows = frappe.get_all(
		"Encargo",
		filters={"source_type": "KNOWN_ITEM", "status": ["!=", "Cancelled"], "expected_item": ["is", "set"]},
		fields=["name", "expected_item"],
	)
	for row in rows:
		if frappe.db.exists("Item", row.expected_item):
			frappe.db.set_value("Encargo", row.name, known_item_values(row.expected_item), update_modified=False)
