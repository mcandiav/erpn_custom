import frappe

from erpn_custom.encargo.reception import RECEPTOR_ROLE


def execute():
	# Pre model sync: the Recepción Chile page lists this role. Desk access without DocType permissions.
	if not frappe.db.exists("Role", RECEPTOR_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": RECEPTOR_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)
	else:
		frappe.db.set_value("Role", RECEPTOR_ROLE, "desk_access", 1)
	frappe.clear_cache()
