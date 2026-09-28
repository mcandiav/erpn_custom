import frappe
from frappe.permissions import add_permission, update_permission_property

SELLER_ROLE = "ComercialFRA"
# Delete stays with higher roles; the seller works the order end to end.
PTYPES = {
	"Sales Order": ("read", "write", "create", "submit", "cancel", "amend", "print", "report"),
	"Encargo": ("read", "write", "create", "print", "report"),
	# ERPNext creates it on order submit and cancels it on order cancel, as the current user;
	# Document.save checks write before submit.
	"Stock Reservation Entry": ("read", "write", "create", "submit", "cancel", "report"),
}


def execute():
	if not frappe.db.exists("Role", SELLER_ROLE):
		return
	for doctype, ptypes in PTYPES.items():
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": SELLER_ROLE, "permlevel": 0}):
			add_permission(doctype, SELLER_ROLE, 0)
		for ptype in ptypes:
			update_permission_property(doctype, SELLER_ROLE, 0, ptype, 1)
	frappe.clear_cache()
