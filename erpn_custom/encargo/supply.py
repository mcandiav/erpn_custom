"""Spec 017 §12: supply status per Sales Order line and the Shopper confirmation before submit.

Spec 020: the figures come from demand.summarize (supply events + reception units).
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM, barcode_exception, demand

COVERED = "Cubierto"
PENDING = "Demanda pendiente"
PURCHASED = "Comprado"
EXCEPTION = "Excepción barcode"
REJECTED = barcode_exception.REJECTED_LABEL
RECEPTION = "Recepción pendiente"
RECEIVED = "Recibido / apartado"
CANCELLED = "Cancelado"
ENCARGO_FIELDS = [
	"name",
	"status",
	"source_type",
	"sales_order_item",
	"requested_qty",
	"materialized_qty",
]


def fit(buckets, qty):
	"""Keeps the order and never exceeds qty; empty buckets are dropped."""
	result, left = [], flt(qty)
	for label, value in buckets:
		value = min(max(flt(value), 0), left)
		if value > 0:
			result.append((label, value))
			left -= value
	return result


def encargo_buckets(enc, totals):
	"""[(label, qty)] of one Encargo still on its order line.

	Known Items: received units and assigned stock are reserved on the line itself -> covered.
	Unknown Items: materialized units already moved to their own line (Spec 019) and are left out.
	"""
	materialized = flt(enc.get("materialized_qty"))
	qty = max(flt(enc.get("requested_qty")) - materialized, 0)
	if enc.get("status") == "Cancelled":
		return [(CANCELLED, qty)]
	arrived = totals.received_qty + totals.legacy_qty
	if enc.get("source_type") == "KNOWN_ITEM":
		ready = (COVERED, arrived + totals.stock_qty)
	else:
		ready = (RECEIVED, max(arrived - materialized, 0))
	return fit(
		[
			ready,
			(RECEPTION, totals.waiting_qty),
			(PURCHASED, totals.pending_receive_qty - totals.exception_qty),
			(EXCEPTION, totals.exception_qty),
			(PENDING, totals.pending_supply_qty),
		],
		qty,
	)


def line_buckets(line_qty, encargo_bucket_lists, order_cancelled=False):
	"""Quantities that always add up to the line qty (Spec 017 §12.1)."""
	line_qty = flt(line_qty)
	if order_cancelled:
		return [(CANCELLED, line_qty)] if line_qty else []
	merged = {}
	for buckets in encargo_bucket_lists:
		for label, qty in buckets:
			if label != CANCELLED and qty > 0:
				merged[label] = merged.get(label, 0) + qty
	# What no Encargo explains is stock committed when the order was submitted.
	covered = max(line_qty - sum(q for label, q in merged.items() if label != COVERED), 0)
	order = [COVERED, PENDING, PURCHASED, EXCEPTION, REJECTED, RECEPTION, RECEIVED]
	result = [(COVERED, covered)] if covered > 0 else []
	result += [(label, merged[label]) for label in order[1:] if label in merged]
	return result


def encargo_totals(encargos):
	"""{encargo: demand.summarize(...)} with two queries for the whole order."""
	names = [e.name for e in encargos]
	events, units = {}, {}
	if names:
		for row in frappe.get_all(
			demand.EVENT,
			filters={"parenttype": "Encargo", "parent": ("in", names)},
			fields=["parent", *demand.EVENT_FIELDS],
			order_by="idx asc",
		):
			events.setdefault(row.parent, []).append(row)
		for row in frappe.get_all(demand.UNIT, filters={"encargo": ("in", names)}, fields=["encargo", *demand.UNIT_FIELDS]):
			units.setdefault(row.encargo, []).append(row)
	return {
		e.name: demand.summarize(e.requested_qty, events.get(e.name, []), units.get(e.name, [])) for e in encargos
	}


def summary(buckets):
	return " / ".join(f"{frappe.format_value(qty, 'Float')} {_(label).lower()}" for label, qty in buckets)


def _line_of(enc, lines_by_name, lines_by_encargo):
	if enc.sales_order_item in lines_by_name:
		return enc.sales_order_item
	return lines_by_encargo.get(enc.name)


@frappe.whitelist()
def order_supply(sales_order):
	doc = frappe.get_doc("Sales Order", sales_order)
	doc.check_permission("read")
	lines_by_name = {item.name: item for item in doc.items}
	lines_by_encargo = {item.custom_encargo: item.name for item in doc.items if item.get("custom_encargo")}
	encargos = frappe.get_all("Encargo", filters={"sales_order": doc.name}, fields=ENCARGO_FIELDS)
	totals = encargo_totals(encargos)
	per_line = {}
	for enc in encargos:
		line = _line_of(enc, lines_by_name, lines_by_encargo)
		if line:
			per_line.setdefault(line, []).append(encargo_buckets(enc, totals[enc.name]))
	for item in doc.items:
		if item.get("custom_encargo_origin") and not item.get("custom_encargo"):
			# Materialized line: its unit was received and assigned to this order.
			per_line[item.name] = [[(RECEIVED, flt(item.qty))]]
	lines = []
	for item in doc.items:
		buckets = line_buckets(item.qty, per_line.get(item.name, []), doc.docstatus == 2)
		lines.append(
			{
				"idx": item.idx,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": flt(item.qty),
				"buckets": [{"label": _(label), "qty": qty} for label, qty in buckets],
				"summary": summary(buckets),
			}
		)
	return {"lines": lines}


@frappe.whitelist(methods=["POST"])
def shopper_preview(items, set_warehouse=None):
	"""Shortfall of the form lines as they are now, computed exactly like before_submit."""
	from erpn_custom.encargo import sales_order_encargo

	if not frappe.has_permission("Sales Order", "submit"):
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	rows = [frappe._dict(row) for row in frappe.parse_json(items) or []]
	for row in rows:
		row.qty = flt(row.qty)
		row.pop("is_stock_item", None)
	split = sales_order_encargo.stock_split(rows, set_warehouse)
	lines = []
	for row in rows:
		_stock, shortfall = split[id(row)]
		if shortfall > 0 and row.item_code != ENCARGO_PENDIENTE_ITEM:
			lines.append({"idx": row.idx, "item_code": row.item_code, "qty": row.qty, "shopper_qty": shortfall})
	return {"total": sum(line["shopper_qty"] for line in lines), "lines": lines}
