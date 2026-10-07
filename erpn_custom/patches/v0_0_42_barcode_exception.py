import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	ensure_sales_order_fields()
	map_waiting_units()


def ensure_sales_order_fields():
	create_custom_fields(
		{
			"Sales Order": [
				{
					"fieldname": "custom_shopper_qty_confirmed",
					"label": "Unidades al Shopper confirmadas",
					"fieldtype": "Data",
					"insert_after": "set_warehouse",
					"hidden": 1,
					"no_copy": 1,
					"print_hide": 1,
				},
			]
		},
		ignore_validate=True,
		update=True,
	)


def map_waiting_units():
	"""Spec 017 §10: units waiting in PENDING_BARCODE_APPROVAL become an Encargo exception.

	Historical purchases stay empty; UNKNOWN_ITEM has no expected Item to approve against.
	Spec 020: the exception and its ToDo now live on the purchase event (v0_0_43_supply_events).
	"""
	encargos = frappe.db.sql_list(
		"""select distinct e.name from `tabRecepcion Unidad` u
		inner join `tabEncargo` e on e.name = u.encargo
		where u.status='PENDING_BARCODE_APPROVAL' and e.source_type='KNOWN_ITEM'
			and e.purchase_status='PURCHASED' and e.status='Open'
			and ifnull(e.barcode_exception_status, '') in ('', 'NOT_APPLICABLE', 'PENDING_APPROVAL')"""
	)
	for encargo in encargos:
		frappe.db.set_value("Encargo", encargo, "barcode_exception_status", "PENDING_APPROVAL", update_modified=False)
