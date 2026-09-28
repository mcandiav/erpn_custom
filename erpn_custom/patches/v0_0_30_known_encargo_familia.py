import frappe

from erpn_custom.encargo.sales_order_line import LINE_FIELDS, sync_sales_order_line
from erpn_custom.patches.v0_0_28_known_encargo_item_fields import execute as refresh_known_encargos


def execute():
	# Known-item Encargos now also copy the Item familia.
	refresh_known_encargos()
	# Draft order lines show the Encargo characteristics and image.
	for encargo in frappe.get_all(
		"Encargo",
		filters={"source_type": "UNKNOWN_ITEM", "sales_order_item": ["is", "set"]},
		fields=["source_type", "sales_order", "sales_order_item", *LINE_FIELDS],
	):
		sync_sales_order_line(encargo)
