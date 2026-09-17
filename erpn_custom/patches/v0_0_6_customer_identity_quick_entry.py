import frappe


def execute():
	"""Frappe v16 uses allow_in_quick_entry (not in_quick_entry)."""
	for fieldname in ("custom_tax_id_type", "custom_tax_id_country"):
		name = frappe.db.get_value(
			"Custom Field", {"dt": "Customer", "fieldname": fieldname}, "name"
		)
		if name:
			frappe.db.set_value("Custom Field", name, "allow_in_quick_entry", 1)
	frappe.clear_cache(doctype="Customer")
