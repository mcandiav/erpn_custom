import frappe

from erpn_custom.encargo.reception import RECEPTOR_ROLE


def execute():
	# The receptor only scans: every read and write goes through erpn_custom.encargo.reception.
	rows = frappe.get_all("Custom DocPerm", filters={"role": RECEPTOR_ROLE}, fields=["name", "parent"])
	for row in rows:
		frappe.delete_doc("Custom DocPerm", row.name, ignore_permissions=True, force=True)
	for doctype in {row.parent for row in rows}:
		frappe.clear_cache(doctype=doctype)
	frappe.clear_cache()
