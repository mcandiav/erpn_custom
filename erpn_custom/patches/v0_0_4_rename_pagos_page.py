import frappe


def execute():
	if frappe.db.exists("Page", "pagos-de-clientes"):
		frappe.delete_doc("Page", "pagos-de-clientes", force=1, ignore_permissions=True)
