import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	ensure_sales_order_item_fields()
	backfill_encargos()
	mark_units_to_link()


def ensure_sales_order_item_fields():
	create_custom_fields(
		{
			"Sales Order Item": [
				{
					"fieldname": "custom_encargo_origin",
					"label": "Encargo de origen",
					"fieldtype": "Link",
					"options": "Encargo",
					"insert_after": "custom_encargo_qty",
					"read_only": 1,
					"no_copy": 1,
				},
				{
					"fieldname": "custom_encargo_source_row",
					"label": "Línea ENCARGO-PENDIENTE de origen",
					"fieldtype": "Data",
					"insert_after": "custom_encargo_origin",
					"read_only": 1,
					"no_copy": 1,
				},
			]
		},
		ignore_validate=True,
		update=True,
	)


def backfill_encargos():
	frappe.db.sql(
		"""update `tabEncargo`
		set materialized_qty=ifnull(materialized_qty, 0),
			pending_materialize_qty=if(source_type='UNKNOWN_ITEM',
				greatest(ifnull(requested_qty, 0) - ifnull(materialized_qty, 0), 0), 0)"""
	)


def mark_units_to_link():
	"""Units received before Spec 019 wait in Pendientes de vincular a OV; ComercialFRA retries them."""
	frappe.db.sql(
		"""update `tabRecepcion Unidad` u
		inner join `tabEncargo` e on e.name = u.encargo
		set u.materialization_status='PENDING'
		where u.status='POSTED' and u.destination='ENCARGO'
			and e.source_type='UNKNOWN_ITEM' and ifnull(u.materialization_status, '')=''"""
	)
