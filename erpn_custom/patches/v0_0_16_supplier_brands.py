import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpn_custom.patches.v0_0_15_brand_supplier import ensure_item_brand_supplier_field


def execute():
	ensure_supplier_brand_table()
	ensure_item_brand_supplier_field()
	_refresh_item_supplier_label()


def ensure_supplier_brand_table():
	create_custom_fields(
		{
			"Supplier": [
				{
					"fieldname": "custom_supplied_brands_section",
					"label": "Marcas proveídas",
					"fieldtype": "Section Break",
					"insert_after": "supplier_name",
					"collapsible": 1,
				},
				{
					"fieldname": "custom_supplied_brands",
					"label": "Marcas proveídas",
					"fieldtype": "Table",
					"options": "Supplier Brand",
					"insert_after": "custom_supplied_brands_section",
					"description": "Marcas que este proveedor vende (ej. Ross: casi todas excepto Zadig). El shopper no usa esta lista.",
				},
			]
		},
		ignore_validate=True,
		update=True,
	)


def _refresh_item_supplier_label():
	name = frappe.db.exists("Custom Field", {"dt": "Item", "fieldname": "custom_brand_supplier"})
	if not name:
		return
	doc = frappe.get_doc("Custom Field", name)
	doc.label = "Proveedor sugerido"
	doc.description = (
		"Sugerencia de dónde comprar. Opcional: el shopper puede cambiarlo. "
		"Solo aparecen proveedores que listan la Marca del producto."
	)
	doc.save(ignore_permissions=True)
