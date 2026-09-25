import frappe
from frappe.permissions import add_permission, update_permission_property

SELLER_ROLE = "ComercialFRA"
READ_ONLY = ("Brand", "Supplier")
ENCARGO_PTYPES = ("read", "write", "create", "print", "report")


def execute():
	_remove_sales_user_rows_from_v0_0_17()
	if not frappe.db.exists("Role", SELLER_ROLE):
		return
	for doctype in READ_ONLY:
		_ensure(doctype, ("read", "select"))
	_ensure("Encargo", ENCARGO_PTYPES)
	frappe.clear_cache()


def _ensure(doctype, ptypes):
	if not _has_row(doctype):
		add_permission(doctype, SELLER_ROLE, 0)
	for ptype in ptypes:
		update_permission_property(doctype, SELLER_ROLE, 0, ptype, 1)


def _has_row(doctype):
	return bool(
		frappe.db.exists(
			"Custom DocPerm",
			{"parent": doctype, "role": SELLER_ROLE, "permlevel": 0},
		)
	)


def _remove_sales_user_rows_from_v0_0_17():
	# v0_0_17 (briefly shipped) may have granted Sales User read on Brand/Supplier.
	for doctype in READ_ONLY:
		if frappe.db.exists("DocPerm", {"parent": doctype, "role": "Sales User", "permlevel": 0}):
			continue
		for name in frappe.get_all(
			"Custom DocPerm",
			filters={"parent": doctype, "role": "Sales User", "permlevel": 0},
			pluck="name",
		):
			frappe.delete_doc("Custom DocPerm", name, force=1, ignore_permissions=True)
