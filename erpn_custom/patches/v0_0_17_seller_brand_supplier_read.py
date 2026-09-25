import frappe
from frappe.permissions import add_permission, update_permission_property

SELLER_ROLE = "Sales User"
DOCTYPES = ("Brand", "Supplier")


def execute():
	if not frappe.db.exists("Role", SELLER_ROLE):
		return
	for doctype in DOCTYPES:
		if _has_read(doctype):
			continue
		add_permission(doctype, SELLER_ROLE, 0)
		for ptype in ("read", "select"):
			update_permission_property(doctype, SELLER_ROLE, 0, ptype, 1)
	frappe.clear_cache()


def _has_read(doctype):
	for dt in ("Custom DocPerm", "DocPerm"):
		if frappe.db.exists(
			dt,
			{"parent": doctype, "role": SELLER_ROLE, "permlevel": 0, "read": 1},
		):
			return True
	return False
