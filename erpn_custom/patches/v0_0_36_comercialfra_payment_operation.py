import frappe
from frappe.permissions import add_permission, update_permission_property

from erpn_custom.chile.payment_roles import SELLER_ROLE

# Read only: posting runs through the controlled backend (chile.elevation), never DocType rights.
READ_ONLY = ("Bank Transaction", "Known Payer")
ROLE_TARGETS = (
	("Workspace", "Pagos de Clientes"),
	("Page", "pagos-huerfanos"),
	("Page", "vinculador-pagos"),
)


def execute():
	if not frappe.db.exists("Role", SELLER_ROLE):
		return
	for doctype in READ_ONLY:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": SELLER_ROLE, "permlevel": 0}):
			add_permission(doctype, SELLER_ROLE, 0)
		update_permission_property(doctype, SELLER_ROLE, 0, "read", 1)
	for parenttype, parent in ROLE_TARGETS:
		_ensure_role(parenttype, parent)
	frappe.clear_cache()


def _ensure_role(parenttype, parent):
	if not frappe.db.exists(parenttype, parent):
		return
	if frappe.db.exists("Has Role", {"parenttype": parenttype, "parent": parent, "role": SELLER_ROLE}):
		return
	doc = frappe.get_doc(parenttype, parent)
	row = doc.append("roles", {"role": SELLER_ROLE})
	row.db_insert()
