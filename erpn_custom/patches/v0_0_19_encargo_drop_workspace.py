import frappe

from erpn_custom.encargo.desktop_contract import ENCARGO_ITEMS, ENCARGO_SIDEBAR

# Workspace "Encargo" shared the /desk/encargo route with the Encargo list, so the
# sidebar link reopened the workspace. Navigation lives in the sidebar only.
LEGACY_WORKSPACE = "Encargo"


def execute():
	if frappe.db.exists("Workspace", LEGACY_WORKSPACE):
		frappe.delete_doc("Workspace", LEGACY_WORKSPACE, force=1, ignore_permissions=True)
	if frappe.db.exists("Workspace Sidebar", ENCARGO_SIDEBAR):
		doc = frappe.get_doc("Workspace Sidebar", ENCARGO_SIDEBAR)
		doc.set("items", list(ENCARGO_ITEMS))
		doc.save(ignore_permissions=True)
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()
