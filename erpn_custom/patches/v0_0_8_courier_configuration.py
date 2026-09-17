import frappe

from erpn_custom.chile.mcv_desktop_contract import (
	CHILEXPRESS_SETTINGS,
	COURIER_CONFIGURATION,
	COURIER_ITEMS,
	COURIER_SIDEBAR,
)


def execute():
	_ensure_chilexpress_provider()
	_delete_legacy_chilexpress_settings()
	_upsert_courier_sidebar()
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


def _ensure_chilexpress_provider():
	if frappe.db.exists("Courier Provider", "chilexpress"):
		doc = frappe.get_doc("Courier Provider", "chilexpress")
		doc.provider_name = "Chilexpress"
		doc.enabled = 1
		doc.save(ignore_permissions=True)
		return
	frappe.get_doc(
		{
			"doctype": "Courier Provider",
			"provider_name": "Chilexpress",
			"provider_code": "chilexpress",
			"enabled": 1,
			"description": "Courier Chilexpress",
		}
	).insert(ignore_permissions=True)


def _delete_legacy_chilexpress_settings():
	if not frappe.db.exists("DocType", CHILEXPRESS_SETTINGS):
		return
	# Metadata can exist without a physical table (orphan from Spec 007).
	if frappe.db.table_exists(CHILEXPRESS_SETTINGS):
		frappe.db.delete(CHILEXPRESS_SETTINGS)
	frappe.delete_doc("DocType", CHILEXPRESS_SETTINGS, force=1, ignore_permissions=True)


def _upsert_courier_sidebar():
	items = list(COURIER_ITEMS)
	if not frappe.db.exists("DocType", COURIER_CONFIGURATION):
		frappe.log_error(
			title="Spec 008: Courier Configuration missing",
			message="DocType Courier Configuration not found; Courier sidebar created without items.",
		)
		items = []

	values = {
		"doctype": "Workspace Sidebar",
		"title": COURIER_SIDEBAR,
		"header_icon": "truck",
		"module": "Chile",
		"standard": 1,
		"app": "erpn_custom",
	}
	if frappe.db.exists("Workspace Sidebar", COURIER_SIDEBAR):
		doc = frappe.get_doc("Workspace Sidebar", COURIER_SIDEBAR)
		doc.update(values)
		doc.set("items", items)
		doc.save(ignore_permissions=True)
		return
	doc = frappe.get_doc(values)
	doc.set("items", items)
	doc.insert(ignore_permissions=True)
