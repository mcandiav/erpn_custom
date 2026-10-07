"""Spec 017 §12: supply status per Sales Order line and the Shopper confirmation before submit."""

import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM, barcode_exception

COVERED = "Cubierto por stock"
PENDING = "Demanda pendiente"
PURCHASED = "Comprado"
EXCEPTION = "Excepción barcode"
REJECTED = barcode_exception.REJECTED_LABEL
RECEPTION = "Recepción pendiente"
RECEIVED = "Recibido / apartado"
CANCELLED = "Cancelado"
PRE_018_RECEIVED = ("RECEIVED", "RESOLVED_TO_ENC", "RESOLVED_TO_STOCK")
WAITING_UNIT_STATUSES = (
	"PENDING_CLASSIFICATION",
	"PENDING_BARCODE_APPROVAL",
	"PENDING_COST",
	"PENDING_CONFIGURATION",
)
ENCARGO_FIELDS = [
	"name",
	"status",
	"sales_order_item",
	"requested_qty",
	"received_qty",
	"purchase_status",
	"reception_status",
	"barcode_exception_status",
]


def encargo_buckets(enc, waiting_units=0):
	"""[(label, qty)] of one Encargo; a purchase splits into received / in reception / in transit."""
	qty = flt(enc.get("requested_qty"))
	if enc.get("status") == "Cancelled":
		return [(CANCELLED, qty)]
	if enc.get("purchase_status") != "PURCHASED":
		return [(PENDING, qty)]
	exception = enc.get("barcode_exception_status")
	if exception == barcode_exception.PENDING_APPROVAL:
		return [(EXCEPTION, qty)]
	if exception == barcode_exception.REJECTED:
		return [(REJECTED, qty)]
	received = flt(enc.get("received_qty"))
	if not received and enc.get("reception_status") in PRE_018_RECEIVED:
		received = qty
	received = min(received, qty)
	waiting = min(flt(waiting_units), qty - received)
	return [(RECEIVED, received), (RECEPTION, waiting), (PURCHASED, qty - received - waiting)]


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
	covered = max(line_qty - sum(merged.values()), 0)
	order = [COVERED, PENDING, PURCHASED, EXCEPTION, REJECTED, RECEPTION, RECEIVED]
	result = [(COVERED, covered)] if covered > 0 else []
	result += [(label, merged[label]) for label in order[1:] if label in merged]
	return result


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
	waiting = {}
	if encargos:
		for row in frappe.get_all(
			"Recepcion Unidad",
			filters={"encargo": ("in", [e.name for e in encargos]), "status": ("in", WAITING_UNIT_STATUSES)},
			fields=["encargo"],
		):
			waiting[row.encargo] = waiting.get(row.encargo, 0) + 1
	per_line = {}
	for enc in encargos:
		line = _line_of(enc, lines_by_name, lines_by_encargo)
		if line:
			per_line.setdefault(line, []).append(encargo_buckets(enc, waiting.get(enc.name, 0)))
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
