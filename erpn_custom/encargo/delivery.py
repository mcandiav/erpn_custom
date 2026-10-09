"""Spec 017 §15 (decision A): on orders with Encargos a Delivery Note delivers only what the line has reserved.

ERPNext checks only that the warehouse is one of the reserved ones, not the quantity. Stock available but not
reserved is first assigned with "Asignar stock a demanda" (Spec 020 §14). Units of purchases pending barcode
approval or rejected never hold a reservation for the line, so they are never deliverable.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM

SRE = "Stock Reservation Entry"


def excess(rows, reserved):
	"""[(row, reserved_qty)] for rows asking more than their line holds reserved in that warehouse."""
	asked, result = {}, []
	for row in rows:
		key = (row.get("so_detail"), row.get("warehouse"))
		asked[key] = asked.get(key, 0) + flt(row.get("stock_qty") or row.get("qty"))
		if asked[key] > flt(reserved.get(key)) + 1e-9:
			result.append((row, flt(reserved.get(key))))
	return result


def _orders_with_encargo(orders):
	if not orders:
		return set()
	return set(
		frappe.get_all(
			"Encargo",
			filters={"sales_order": ("in", list(orders)), "status": ("!=", "Cancelled")},
			pluck="sales_order",
		)
	)


def _reserved(lines):
	reserved = {}
	for sre in frappe.get_all(
		SRE,
		filters={"voucher_type": "Sales Order", "voucher_detail_no": ("in", list(lines)), "docstatus": 1},
		fields=["voucher_detail_no", "warehouse", "reserved_qty", "delivered_qty"],
	):
		key = (sre.voucher_detail_no, sre.warehouse)
		reserved[key] = reserved.get(key, 0) + max(flt(sre.reserved_qty) - flt(sre.delivered_qty), 0)
	return reserved


def validate_reserved_delivery(doc, method=None):
	"""Delivery Note validate: runs after ERPNext set each row's warehouse from its reservations."""
	if doc.get("is_return"):
		return
	rows = [
		row
		for row in doc.get("items") or []
		if row.get("against_sales_order") and row.get("so_detail") and row.item_code != ENCARGO_PENDIENTE_ITEM
	]
	orders = _orders_with_encargo({row.against_sales_order for row in rows})
	rows = [row for row in rows if row.against_sales_order in orders]
	if not rows:
		return
	problems = excess(rows, _reserved({row.so_detail for row in rows}))
	if not problems:
		return
	frappe.throw(
		"<br>".join(
			_("Fila {0}: {1} de {2} tiene {3} unidad(es) reservada(s) en {4}.").format(
				row.idx, row.item_code, row.against_sales_order, f"{held:g}", row.warehouse
			)
			for row, held in problems
		)
		+ "<br>"
		+ _("Para entregar stock disponible, primero usa \"Asignar stock a demanda\" en el Encargo de la línea."),
		title=_("Cantidad sin reserva"),
	)
