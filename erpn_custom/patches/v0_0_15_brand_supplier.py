import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpn_custom.chile.mcv_desktop_contract import ROOT_FOLDER
from erpn_custom.encargo.desktop_contract import ENCARGO_ITEMS, ENCARGO_SIDEBAR


def execute():
	ensure_item_brand_supplier_field()
	_drop_legacy_item_pair_field()
	_drop_legacy_encargo_pair_columns()
	_delete_legacy_pair_doctypes()
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


def ensure_item_brand_supplier_field():
	create_custom_fields(
		{
			"Item": [
				{
					"fieldname": "custom_encargo_section",
					"label": "Origen Marca / Proveedor",
					"fieldtype": "Section Break",
					"insert_after": "brand",
					"collapsible": 1,
				},
				{
					"fieldname": "custom_brand_supplier",
					"label": "Proveedor de marca",
					"fieldtype": "Link",
					"options": "Supplier",
					"insert_after": "custom_encargo_section",
					"description": "Distribuidor de esta marca para este producto. Colecciones distintas = productos distintos (ej. MK Outlet vs MK Tienda).",
				},
			]
		},
		ignore_validate=True,
		update=True,
	)


def _drop_legacy_item_pair_field():
	name = frappe.db.exists("Custom Field", {"dt": "Item", "fieldname": "custom_encargo_brand_store"})
	if name:
		frappe.delete_doc("Custom Field", name, force=1, ignore_permissions=True)


def _drop_legacy_encargo_pair_columns():
	if not frappe.db.exists("DocType", "Encargo"):
		return
	for column in ("encargo_brand_store", "suggested_store"):
		try:
			if frappe.db.has_column("Encargo", column):
				frappe.db.sql_ddl(f"alter table `tabEncargo` drop column `{column}`")
		except Exception:
			frappe.log_error(title=f"v0_0_15 drop column {column}")


def _delete_legacy_pair_doctypes():
	for dt in ("Encargo Brand Store", "Encargo Store"):
		if frappe.db.exists("DocType", dt):
			frappe.delete_doc("DocType", dt, force=1, ignore_permissions=True)


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
