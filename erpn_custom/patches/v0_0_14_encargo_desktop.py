import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpn_custom.chile.mcv_desktop_contract import ROOT_FOLDER
from erpn_custom.encargo.desktop_contract import ENCARGO_ITEMS, ENCARGO_SIDEBAR


def execute():
	ensure_item_encargo_brand_store_field()
	_upsert_encargo_sidebar()
	_upsert_icon(
		{
			"doctype": "Desktop Icon",
			"label": ENCARGO_SIDEBAR,
			"icon": "shopping-bag",
			"icon_type": "Link",
			"idx": 3,
			"link_to": ENCARGO_SIDEBAR,
			"link_type": "Workspace Sidebar",
			"parent_icon": ROOT_FOLDER,
			"hidden": 0,
			"standard": 1,
			"app": "erpn_custom",
			"bg_color": "blue",
			"restrict_removal": 0,
		}
	)
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


def ensure_item_encargo_brand_store_field():
	create_custom_fields(
		{
			"Item": [
				{
					"fieldname": "custom_encargo_section",
					"label": "Origen Encargo",
					"fieldtype": "Section Break",
					"insert_after": "brand",
					"collapsible": 1,
				},
				{
					"fieldname": "custom_encargo_brand_store",
					"label": "Marca / Tienda",
					"fieldtype": "Link",
					"options": "Encargo Brand Store",
					"insert_after": "custom_encargo_section",
					"description": "Par Marca+Tienda de origen (ej. Michael Kors — Outlet). Colecciones distintas = productos distintos.",
				},
			]
		},
		ignore_validate=True,
		update=True,
	)


def _upsert_encargo_sidebar():
	values = {
		"doctype": "Workspace Sidebar",
		"title": ENCARGO_SIDEBAR,
		"header_icon": "shopping-bag",
		"module": "Encargo",
		"standard": 1,
		"app": "erpn_custom",
	}
	if frappe.db.exists("Workspace Sidebar", ENCARGO_SIDEBAR):
		doc = frappe.get_doc("Workspace Sidebar", ENCARGO_SIDEBAR)
		doc.update(values)
		doc.set("items", list(ENCARGO_ITEMS))
		doc.save(ignore_permissions=True)
		return
	doc = frappe.get_doc(values)
	doc.set("items", list(ENCARGO_ITEMS))
	doc.insert(ignore_permissions=True)


def _upsert_icon(values):
	label = values["label"]
	existing = frappe.db.exists("Desktop Icon", {"label": label, "standard": 1})
	if existing:
		doc = frappe.get_doc("Desktop Icon", existing)
		doc.update(values)
		doc.save(ignore_permissions=True)
		return
	frappe.get_doc(values).insert(ignore_permissions=True)
