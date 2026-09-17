import frappe

SCRIPT_NAME = "Validar y normalizar RUT Cliente"


def execute():
	if not frappe.db.exists("Server Script", SCRIPT_NAME):
		return
	doc = frappe.get_doc("Server Script", SCRIPT_NAME)
	if doc.disabled:
		return
	doc.disabled = 1
	doc.save(ignore_permissions=True)
