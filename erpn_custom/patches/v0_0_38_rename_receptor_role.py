import frappe

from erpn_custom.encargo.reception import RECEPTOR_ROLE

OLD_ROLE = "ReceptorFRA"


def execute():
	# Sites that already ran v0_0_37 with the first name; rename carries its users and permissions.
	if not frappe.db.exists("Role", OLD_ROLE) or frappe.db.exists("Role", RECEPTOR_ROLE):
		return
	frappe.rename_doc("Role", OLD_ROLE, RECEPTOR_ROLE, force=True, ignore_permissions=True, show_alert=False)
	frappe.db.set_value("Role", RECEPTOR_ROLE, "role_name", RECEPTOR_ROLE)
	frappe.clear_cache()
