import frappe
from frappe.permissions import add_permission, update_permission_property

from erpn_custom.encargo.reception import RECEPTOR_ROLE

# Reception reads Encargos and creates the real Item; state changes and Item barcodes go through
# erpn_custom.encargo.reception, never through direct writes.
PERMISSIONS = {
	"Encargo": ("read", "report", "print"),
	"Item": ("read", "select", "create", "report"),
	"Brand": ("read", "select"),
	"Item Group": ("read", "select"),
	"UOM": ("read", "select"),
	"Supplier": ("read", "select"),
}


def execute():
	# Pre model sync: the Recepción Chile page lists this role.
	if not frappe.db.exists("Role", RECEPTOR_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": RECEPTOR_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)
	else:
		frappe.db.set_value("Role", RECEPTOR_ROLE, "desk_access", 1)
	for doctype, ptypes in PERMISSIONS.items():
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": RECEPTOR_ROLE, "permlevel": 0}):
			add_permission(doctype, RECEPTOR_ROLE, 0)
		for ptype in ptypes:
			update_permission_property(doctype, RECEPTOR_ROLE, 0, ptype, 1)
	frappe.clear_cache()
