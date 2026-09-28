import frappe

from erpn_custom.encargo.shopper import SHOPPER_ROLE


def execute():
	# Website role: the shopper never enters the Desk and gets no DocType permission.
	if frappe.db.exists("Role", SHOPPER_ROLE):
		frappe.db.set_value("Role", SHOPPER_ROLE, "desk_access", 0)
		return
	frappe.get_doc({"doctype": "Role", "role_name": SHOPPER_ROLE, "desk_access": 0}).insert(
		ignore_permissions=True
	)
