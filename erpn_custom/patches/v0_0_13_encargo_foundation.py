import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM


def execute():
	ensure_encargo_pendiente_item()
	ensure_sales_order_item_fields()
	ensure_partial_reservation_if_enabled()


def ensure_encargo_pendiente_item():
	if frappe.db.exists("Item", ENCARGO_PENDIENTE_ITEM):
		doc = frappe.get_doc("Item", ENCARGO_PENDIENTE_ITEM)
		changed = False
		if cint(doc.is_stock_item):
			doc.is_stock_item = 0
			changed = True
		if cint(doc.disabled):
			doc.disabled = 0
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return

	item_group = _default_item_group()
	uom = _default_uom()
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": ENCARGO_PENDIENTE_ITEM,
			"item_name": "Encargo pendiente (producto no identificado)",
			"item_group": item_group,
			"stock_uom": uom,
			"is_stock_item": 0,
			"include_item_in_manufacturing": 0,
			"is_sales_item": 1,
			"is_purchase_item": 0,
			"description": "Item técnico no-stock para Sales Order con producto aún no identificado. No representa existencia física.",
		}
	).insert(ignore_permissions=True)


def ensure_sales_order_item_fields():
	create_custom_fields(
		{
			"Sales Order Item": [
				{
					"fieldname": "custom_encargo_section",
					"label": "Encargo",
					"fieldtype": "Section Break",
					"insert_after": "warehouse",
					"collapsible": 1,
				},
				{
					"fieldname": "custom_encargo",
					"label": "Encargo",
					"fieldtype": "Link",
					"options": "Encargo",
					"insert_after": "custom_encargo_section",
					"read_only": 1,
					"no_copy": 1,
				},
				{
					"fieldname": "custom_stock_committed_qty",
					"label": "Stock Committed Qty",
					"fieldtype": "Float",
					"insert_after": "custom_encargo",
					"read_only": 1,
					"no_copy": 1,
					"default": "0",
				},
				{
					"fieldname": "custom_encargo_qty",
					"label": "Encargo Qty",
					"fieldtype": "Float",
					"insert_after": "custom_stock_committed_qty",
					"read_only": 1,
					"no_copy": 1,
					"default": "0",
				},
			]
		},
		ignore_validate=True,
		update=True,
	)


def ensure_partial_reservation_if_enabled():
	if not frappe.db.exists("DocType", "Stock Settings"):
		return
	if not cint(frappe.get_single_value("Stock Settings", "enable_stock_reservation")):
		return
	if cint(frappe.get_single_value("Stock Settings", "allow_partial_reservation")):
		return
	frappe.db.set_single_value("Stock Settings", "allow_partial_reservation", 1)


def _default_item_group():
	for name in ("Products", "All Item Groups"):
		if frappe.db.exists("Item Group", name):
			return name
	groups = frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name", limit=1)
	if groups:
		return groups[0]
	frappe.throw("No Item Group found to create ENCARGO-PENDIENTE")


def _default_uom():
	for name in ("Unidad", "Nos", "Unit"):
		if frappe.db.exists("UOM", name):
			return name
	uoms = frappe.get_all("UOM", pluck="name", limit=1)
	if uoms:
		return uoms[0]
	frappe.throw("No UOM found to create ENCARGO-PENDIENTE")
