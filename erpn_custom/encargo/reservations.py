"""Spec 020 §10 E5: reservations of a Sales Order line against what the Encargo flow says is covered.

Report first; a System Manager repairs from the order ("Revisar reservas"). Only reservations this
flow owns (reception units and stock allocations) are recreated; nothing is rebuilt globally.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.chile.elevation import administrator_context
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM, demand, inventory

SRE = "Stock Reservation Entry"
ADMIN_ROLE = "System Manager"

MISSING = "MISSING"
WRONG_WAREHOUSE = "WRONG_WAREHOUSE"
DUPLICATE = "DUPLICATE"
UNDER_RESERVED = "UNDER_RESERVED"
OVER_RESERVED = "OVER_RESERVED"
OVER_STOCK = "OVER_STOCK"
REPAIRABLE = (MISSING, WRONG_WAREHOUSE, DUPLICATE)
MESSAGES = {
	MISSING: "{source} {name}: su reserva no existe o fue anulada.",
	WRONG_WAREHOUSE: "{source} {name}: está en {warehouse} pero su reserva es de {sre_warehouse}.",
	DUPLICATE: "{source} {name}: comparte la reserva {sre} con otra unidad.",
	UNDER_RESERVED: "Línea {line}: {qty} unidad(es) cubiertas sin reserva vigente.",
	OVER_RESERVED: "Línea {line}: {qty} unidad(es) reservadas de más.",
	OVER_STOCK: "{warehouse}: reservado {reserved} con stock {actual}.",
}


def open_qty(sre):
	"""What the reservation still holds; delivered units no longer need it."""
	if sre.get("docstatus") != 1:
		return 0
	return max(flt(sre.get("reserved_qty")) - flt(sre.get("delivered_qty")), 0)


def expected_reservations(units, events):
	"""One entry per unit this flow committed to the line: live POSTED units and stock allocations."""
	def entry(source, row):
		return {
			"source": source,
			"name": row.get("name"),
			"warehouse": row.get("warehouse"),
			"sre": row.get("stock_reservation_entry"),
		}

	expected = [entry(demand.UNIT, u) for u in units if demand.is_live_unit(u) and u.get("status") == demand.POSTED]
	expected += [
		entry(demand.EVENT, e) for e in events if e.get("source_type") == demand.STOCK and demand.active_qty(e) > 0
	]
	return expected


def reference_problems(expected, sres):
	"""[(code, entry, sre)] for units/allocations whose own reservation is not valid."""
	by_name = {s.get("name"): s for s in sres if s.get("docstatus") == 1}
	used = set()
	problems = []
	for entry in expected:
		sre = by_name.get(entry.get("sre"))
		if not sre:
			problems.append((MISSING, entry, None))
		elif sre.get("warehouse") != entry.get("warehouse"):
			problems.append((WRONG_WAREHOUSE, entry, sre))
		elif entry.get("sre") in used:
			problems.append((DUPLICATE, entry, sre))
		else:
			used.add(entry.get("sre"))
	return problems


def invalid_count(expected, sres):
	"""Units the Encargo cannot call covered: their reservation is gone, elsewhere or shared."""
	return len(reference_problems(expected, sres))


def diagnose_line(line, covered_qty, expected, sres, bins):
	"""Issues of one order line: own references, line totals and warehouses reserved beyond stock."""
	issues = [
		{
			"code": code,
			"source": entry["source"],
			"name": entry["name"],
			"warehouse": entry["warehouse"],
			"sre": entry["sre"],
			"sre_warehouse": sre.get("warehouse") if sre else None,
			"line": line.get("idx"),
		}
		for code, entry, sre in reference_problems(expected, sres)
	]
	reserved = sum(open_qty(s) for s in sres)
	pending_delivery = max(flt(line.get("stock_qty")) - flt(line.get("delivered_qty")), 0)
	needed = min(flt(covered_qty), pending_delivery)
	if reserved < needed:
		issues.append({"code": UNDER_RESERVED, "line": line.get("idx"), "qty": needed - reserved})
	if reserved > pending_delivery:
		issues.append({"code": OVER_RESERVED, "line": line.get("idx"), "qty": reserved - pending_delivery})
	for row in bins:
		if flt(row.get("reserved_stock")) > flt(row.get("actual_qty")):
			issues.append(
				{
					"code": OVER_STOCK,
					"line": line.get("idx"),
					"warehouse": row.get("warehouse"),
					"reserved": flt(row.get("reserved_stock")),
					"actual": flt(row.get("actual_qty")),
				}
			)
	for issue in issues:
		issue["repairable"] = issue["code"] in REPAIRABLE
		issue["message"] = _(MESSAGES[issue["code"]]).format(
			**{
				"source": _(issue.get("source") or ""),
				"name": issue.get("name"),
				"warehouse": issue.get("warehouse"),
				"sre_warehouse": issue.get("sre_warehouse"),
				"sre": issue.get("sre"),
				"line": issue.get("line"),
				"qty": f"{flt(issue.get('qty')):g}",
				"reserved": f"{flt(issue.get('reserved')):g}",
				"actual": f"{flt(issue.get('actual')):g}",
			}
		)
	return issues


def line_sres(sales_order_item):
	return frappe.get_all(
		SRE,
		filters={"voucher_type": "Sales Order", "voucher_detail_no": sales_order_item, "docstatus": 1},
		fields=["name", "docstatus", "status", "warehouse", "reserved_qty", "delivered_qty"],
	)


def encargo_invalid_qty(enc, events, units):
	"""Covered units of a KNOWN_ITEM Encargo whose reservation is not valid (0 for other Encargos)."""
	if enc.get("source_type") != "KNOWN_ITEM" or not enc.get("sales_order_item"):
		return 0
	expected = expected_reservations(units, events)
	if not expected:
		return 0
	return invalid_count(expected, line_sres(enc.get("sales_order_item")))


def _line_inputs(line):
	encargos = frappe.get_all(
		"Encargo",
		filters={"sales_order_item": line.name, "source_type": "KNOWN_ITEM", "status": ("!=", "Cancelled")},
		pluck="name",
	)
	units, events = [], []
	for name in encargos:
		units += frappe.get_all(demand.UNIT, filters={"encargo": name}, fields=demand.UNIT_FIELDS)
		events += frappe.get_all(
			demand.EVENT, filters={"parent": name, "parenttype": "Encargo"}, fields=demand.EVENT_FIELDS
		)
	return encargos, expected_reservations(units, events)


def _lines(doc):
	for line in doc.items:
		if line.item_code == ENCARGO_PENDIENTE_ITEM:
			continue
		if not frappe.get_cached_value("Item", line.item_code, "is_stock_item"):
			continue
		yield line


def _covered_by_line(sales_order):
	from erpn_custom.encargo import supply

	result = {}
	for row in supply.order_supply(sales_order)["lines"]:
		result[row["name"]] = sum(b["qty"] for b in row["buckets"] if b["label"] == _(supply.COVERED))
	return result


def diagnose(sales_order):
	doc = frappe.get_doc("Sales Order", sales_order)
	covered = _covered_by_line(sales_order)
	lines = []
	for line in _lines(doc):
		_encargos, expected = _line_inputs(line)
		sres = line_sres(line.name)
		warehouses = {s.warehouse for s in sres} | {e["warehouse"] for e in expected if e["warehouse"]}
		bins = (
			frappe.get_all(
				"Bin",
				filters={"item_code": line.item_code, "warehouse": ("in", list(warehouses))},
				fields=["warehouse", "actual_qty", "reserved_stock"],
			)
			if warehouses
			else []
		)
		issues = diagnose_line(line, covered.get(line.name, 0), expected, sres, bins)
		lines.append({"idx": line.idx, "name": line.name, "item_code": line.item_code, "issues": issues})
	return lines


@frappe.whitelist()
def review_reservations(sales_order):
	"""Read-only report for the order (System Manager)."""
	frappe.only_for(ADMIN_ROLE)
	lines = diagnose(sales_order)
	return {"sales_order": sales_order, "lines": lines, "issues": sum(len(line["issues"]) for line in lines)}


def _repair_entry(issue, line, item_code, sales_order):
	"""Cancels the stale reservation of one unit/allocation and reserves it again where the unit is."""
	if issue["code"] == WRONG_WAREHOUSE:
		inventory.cancel_reservation(issue["sre"])
	sre, problem = inventory.reserve_unit(sales_order, line, item_code, issue["warehouse"])
	if problem:
		return problem
	frappe.db.set_value(issue["source"], issue["name"], "stock_reservation_entry", sre, update_modified=False)
	if issue["source"] == demand.UNIT:
		frappe.db.set_value(demand.UNIT, issue["name"], "reservation_note", None, update_modified=False)
	else:
		unit = frappe.db.get_value(demand.EVENT, issue["name"], "reception_unit")
		if unit:
			frappe.db.set_value(demand.UNIT, unit, "stock_reservation_entry", sre, update_modified=False)
	return None


@frappe.whitelist(methods=["POST"])
def repair_reservations(sales_order):
	"""Recreates only the reservations this flow owns; line totals and warehouses beyond stock are reported."""
	frappe.only_for(ADMIN_ROLE)
	doc = frappe.get_doc("Sales Order", sales_order)
	if doc.docstatus != 1:
		frappe.throw(_("La Orden de Venta no está validada."))
	frappe.db.get_value("Sales Order", sales_order, "name", for_update=True)
	results = []
	with administrator_context():
		for line in diagnose(sales_order):
			item_code = line["item_code"]
			for issue in line["issues"]:
				if not issue["repairable"]:
					continue
				problem = _repair_entry(issue, line["name"], item_code, sales_order)
				results.append({"line": line["idx"], "name": issue["name"], "ok": not problem, "problem": problem})
		for name in frappe.get_all("Encargo", filters={"sales_order": sales_order}, pluck="name"):
			demand.reconcile_encargo_supply(name)
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Sales Order",
			"reference_name": sales_order,
			"content": _("Reservas corregidas por {0}: {1} ok, {2} con problema.").format(
				frappe.session.user, sum(1 for r in results if r["ok"]), sum(1 for r in results if not r["ok"])
			),
		}
	).insert(ignore_permissions=True)
	return {"sales_order": sales_order, "repaired": results, "after": review_reservations(sales_order)}
