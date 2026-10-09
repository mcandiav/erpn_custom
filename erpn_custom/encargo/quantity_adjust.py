"""Spec 017 §13: quantity changes on a submitted Sales Order that has Encargos.

ERPNext "Update Items" cancels and recreates every Stock Reservation Entry of the order, which would undo the
per-unit reservations of Specs 018/019/020, so it is blocked for those orders. "Ajustar cantidad" changes one
line and touches only that line's own reservations:

- increase (payment gate of Spec 015): stock available now is reserved, the rest goes to the line's Encargo
  (its requested_qty grows, Spec 020 §18) or to a new Encargo when the line has none;
- decrease: first demand still without source, then stock reserved at submit; never what was bought, received,
  set aside, materialized, delivered or billed.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.chile.elevation import administrator_context
from erpn_custom.chile.sales_order_credit import applied_to_order
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM, barcode_exception, demand, inventory, materialization, reservations

ADJUST_ROLES = ("Sales Manager", "System Manager")
REASON_MAX = 1000
KNOWN, UNKNOWN = "KNOWN", "UNKNOWN"
ENCARGO_FIELDS = ["name", "status", "source_type", "requested_qty", "materialized_qty", "sales_order_item"]


def known_increase(delta, available):
	"""(units reserved from stock available now, units added to the Encargo)."""
	stock = min(int(delta), max(int(flt(available)), 0))
	return stock, int(delta) - stock


def known_decrease(delta, unsourced, committed_open):
	"""(cut from demand without source, cut from stock reserved at submit, units that cannot be cut)."""
	encargo_cut = min(int(delta), max(int(flt(unsourced)), 0))
	stock_cut = min(int(delta) - encargo_cut, max(int(flt(committed_open)), 0))
	return encargo_cut, stock_cut, int(delta) - encargo_cut - stock_cut


def can_adjust(user, roles, responsible_users):
	return user in responsible_users or bool(set(ADJUST_ROLES) & set(roles))


def line_kind(line):
	if line.get("item_code") == ENCARGO_PENDIENTE_ITEM:
		return UNKNOWN
	if line.get("custom_encargo_origin") and not line.get("custom_encargo"):
		return None
	return KNOWN


def committed_sres(sres, expected):
	"""Reservations of the line made at submit (or by this action): not owned by a unit or stock allocation."""
	owned = {entry.get("sre") for entry in expected if entry.get("sre")}
	return [s for s in sres if s.get("name") not in owned]


def _clean_reason(value):
	return (value or "").strip()[:REASON_MAX]


def _whole(value):
	qty = flt(value)
	if qty < 1 or qty != int(qty):
		frappe.throw(_("La nueva cantidad debe ser un número entero mayor o igual a 1."))
	return int(qty)


def has_encargo(sales_order):
	return bool(frappe.db.exists("Encargo", {"sales_order": sales_order, "status": ("!=", "Cancelled")}))


def _authorized(sales_order):
	_tier, users = barcode_exception.responsible_for_order(sales_order)
	return can_adjust(frappe.session.user, frappe.get_roles(), users)


def _line_encargo(line, kind, lock):
	read = (lambda name: demand.lock_encargo(name, ENCARGO_FIELDS)) if lock else (
		lambda name: frappe.db.get_value("Encargo", name, ENCARGO_FIELDS, as_dict=True)
	)
	name = line.get("custom_encargo")
	if not name and kind == KNOWN:
		name = frappe.db.get_value(
			"Encargo", {"sales_order_item": line.name, "status": ("!=", "Cancelled")}, "name"
		)
	enc = read(name) if name else None
	if not enc or enc.status == "Cancelled":
		return None, None
	if lock:
		events, units = demand.locked_events(enc.name), demand.locked_units(enc.name)
	else:
		events = frappe.get_all(demand.EVENT, filters={"parent": enc.name, "parenttype": "Encargo"}, fields=demand.EVENT_FIELDS)
		units = frappe.get_all(demand.UNIT, filters={"encargo": enc.name}, fields=demand.UNIT_FIELDS)
	return enc, demand.summarize(enc.requested_qty, events, units)


def _available(item_code, warehouse):
	from erpn_custom.encargo.sales_order_encargo import _bin_available

	return _bin_available(item_code, warehouse)


def plan(order, line, new_qty, lock=False):
	"""What the adjustment would do; `problem` set when it is not allowed."""
	kind = line_kind(line)
	p = frappe._dict(
		kind=kind,
		line=line.name,
		idx=line.idx,
		item_code=line.item_code,
		old_qty=flt(line.qty),
		new_qty=new_qty,
		delta=new_qty - int(flt(line.qty)),
		warehouse=line.warehouse or order.set_warehouse,
		encargo=None,
		stock_part=0,
		encargo_part=0,
		encargo_cut=0,
		stock_cut=0,
		committed=[],
		problem=None,
	)
	if order.docstatus != 1:
		p.problem = _("La Orden de Venta no está validada.")
	elif not kind:
		p.problem = _("Línea de un Encargo ya materializado: usa la devolución de la unidad (Spec 019).")
	elif kind == KNOWN and not frappe.get_cached_value("Item", line.item_code, "is_stock_item"):
		p.problem = _("El producto no es de inventario.")
	elif flt(line.conversion_factor or 1) != 1:
		p.problem = _("La línea usa otra unidad de medida: ajústala en una nueva OV.")
	elif not p.delta:
		p.problem = _("La cantidad no cambia.")
	if p.problem:
		return p

	enc, totals = _line_encargo(line, kind, lock)
	p.encargo = enc.name if enc else None
	if kind == UNKNOWN and not enc:
		p.problem = _("La línea ENCARGO-PENDIENTE no tiene Encargo abierto.")
		return p

	if p.delta > 0:
		if applied_to_order(order.name) <= 0:
			p.problem = _("La Orden de Venta requiere al menos un pago aplicado para aumentar la cantidad (Spec 015).")
		elif kind == KNOWN:
			p.stock_part, p.encargo_part = known_increase(p.delta, _available(line.item_code, p.warehouse))
		else:
			p.encargo_part = p.delta
		return p

	cut = -p.delta
	if new_qty < flt(line.delivered_qty):
		p.problem = _("Ya se entregaron {0} unidades de esta línea.").format(f"{flt(line.delivered_qty):g}")
		return p
	if flt(line.billed_amt) > 0:
		p.problem = _("La línea ya está facturada: usa la nota de crédito estándar.")
		return p
	unsourced = totals.pending_supply_qty if totals else 0
	if kind == UNKNOWN:
		p.encargo_cut = min(cut, int(unsourced))
		if p.encargo_cut < cut:
			p.problem = _(
				"Solo {0} unidad(es) del Encargo {1} siguen sin compra ni recepción; el resto ya tiene fuente."
			).format(int(unsourced), enc.name)
		return p
	_encargos, expected = reservations._line_inputs(line)
	p.committed = [
		s for s in committed_sres(reservations.line_sres(line.name), expected) if not flt(s.get("delivered_qty"))
	]
	committed_open = sum(reservations.open_qty(s) for s in p.committed)
	p.encargo_cut, p.stock_cut, blocked = known_decrease(cut, unsourced, committed_open)
	if blocked:
		p.problem = _(
			"No se puede bajar {0}: solo {1} sin fuente y {2} reservadas de stock; el resto ya fue comprado, recibido o apartado."
		).format(cut, int(unsourced), int(committed_open))
	return p


def describe(p):
	if p.problem:
		return p.problem
	parts = [_("Fila {0} ({1}): {2} → {3}.").format(p.idx, p.item_code, f"{p.old_qty:g}", p.new_qty)]
	if p.stock_part:
		parts.append(_("{0} se reservan del stock disponible en {1}.").format(p.stock_part, p.warehouse))
	if p.encargo_part:
		parts.append(
			_("{0} faltante(s) van al Encargo {1}.").format(p.encargo_part, p.encargo)
			if p.encargo
			else _("{0} faltante(s) van a un Encargo nuevo.").format(p.encargo_part)
		)
	if p.encargo_cut:
		parts.append(_("{0} se descuentan del faltante del Encargo {1}.").format(p.encargo_cut, p.encargo))
	if p.stock_cut:
		parts.append(_("{0} reservada(s) de stock se liberan.").format(p.stock_cut))
	return " ".join(parts)


def _set_encargo_qty(name, requested, materialized=0):
	values = {"requested_qty": requested}
	if materialized is not None:
		values["pending_materialize_qty"] = max(requested - flt(materialized), 0)
	if requested <= 0:
		values = {"status": "Cancelled"}
	frappe.db.set_value("Encargo", name, values, update_modified=True)
	demand.reconcile_encargo_supply(name)


def _release_committed(p, order, line):
	"""Cancels submit-time reservations of the line and reserves back what stays, one unit each."""
	left = p.stock_cut
	for sre in p.committed:
		if left <= 0:
			break
		held = int(reservations.open_qty(sre))
		inventory.cancel_reservation(sre.name)
		keep = held - min(held, left)
		left -= held - keep
		for _i in range(keep):
			_name, problem = inventory.reserve_unit(order.name, line.name, line.item_code, sre.warehouse)
			if problem:
				frappe.throw(problem)


def _apply_known(p, order, line):
	committed = flt(line.get("custom_stock_committed_qty"))
	encargo_qty = flt(line.get("custom_encargo_qty"))
	if p.delta < 0 and p.stock_cut:
		_release_committed(p, order, line)
	materialization._set_qty(line.name, p.new_qty)
	materialization._refresh_order(order.name)
	for _i in range(p.stock_part):
		_name, problem = inventory.reserve_unit(order.name, line.name, line.item_code, p.warehouse)
		if problem:
			frappe.throw(problem)
	values = {"custom_stock_committed_qty": committed + p.stock_part - p.stock_cut}
	if p.encargo_part or p.encargo_cut:
		values["custom_encargo_qty"] = max(encargo_qty + p.encargo_part - p.encargo_cut, 0)
	if p.encargo:
		enc = frappe.db.get_value("Encargo", p.encargo, ["requested_qty"], as_dict=True)
		requested = flt(enc.requested_qty) + p.encargo_part - p.encargo_cut
		if requested != flt(enc.requested_qty):
			_set_encargo_qty(p.encargo, requested, materialized=None)
	elif p.encargo_part:
		p.encargo = _new_encargo(order, line, p.encargo_part)
		values["custom_encargo"] = p.encargo
	frappe.db.set_value("Sales Order Item", line.name, values, update_modified=False)


def _new_encargo(order, line, qty):
	from erpn_custom.encargo import sales_order_encargo

	origin = sales_order_encargo._item_brand_origin(line.item_code)
	if not origin:
		frappe.throw(_("El Item {0} requiere Marca antes de crear el Encargo.").format(line.item_code))
	name = sales_order_encargo.new_known_encargo(
		order, line, qty, sales_order_encargo._first_sales_person(order), origin, status="Open"
	)
	demand.reconcile_encargo_supply(name)
	return name


def _apply_unknown(p, order, line):
	materialization._set_qty(line.name, p.new_qty)
	materialization._refresh_order(order.name)
	frappe.db.set_value("Sales Order Item", line.name, "custom_encargo_qty", p.new_qty, update_modified=False)
	enc = frappe.db.get_value("Encargo", p.encargo, ["requested_qty", "materialized_qty"], as_dict=True)
	_set_encargo_qty(p.encargo, flt(enc.requested_qty) + p.delta, enc.materialized_qty)


def _audit(doctype, name, text):
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": doctype,
			"reference_name": name,
			"content": text,
		}
	).insert(ignore_permissions=True)


def _adjustable(order):
	return [
		{"name": row.name, "idx": row.idx, "item_code": row.item_code, "qty": flt(row.qty)}
		for row in order.items
		if line_kind(row) == UNKNOWN
		or (line_kind(row) == KNOWN and frappe.get_cached_value("Item", row.item_code, "is_stock_item"))
	]


@frappe.whitelist()
def order_adjust_info(sales_order):
	"""Whether Update Items is blocked and the lines this user may adjust."""
	frappe.has_permission("Sales Order", "read", sales_order, throw=True)
	blocked = has_encargo(sales_order)
	order = frappe.get_doc("Sales Order", sales_order)
	allowed = blocked and order.docstatus == 1 and _authorized(sales_order)
	return {"blocked": blocked, "can_adjust": allowed, "lines": _adjustable(order) if allowed else []}


@frappe.whitelist()
def preview_line_adjustment(sales_order, sales_order_item, new_qty):
	if not _authorized(sales_order):
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	order = frappe.get_doc("Sales Order", sales_order)
	line = materialization._row(order, sales_order_item)
	if not line:
		frappe.throw(_("La línea no pertenece a la Orden de Venta."))
	p = plan(order, line, _whole(new_qty))
	return {"ok": not p.problem, "message": describe(p)}


@frappe.whitelist(methods=["POST"])
def adjust_line_qty(sales_order, sales_order_item, new_qty, reason=None):
	"""Ajustar cantidad de una línea de OV validada con Encargos (Spec 017 §13)."""
	reason = _clean_reason(reason)
	if not reason:
		frappe.throw(_("Indica el motivo."))
	new_qty = _whole(new_qty)
	if not _authorized(sales_order):
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	if not has_encargo(sales_order):
		frappe.throw(_("La Orden de Venta no tiene Encargos: usa Actualizar artículos."))
	order = materialization._lock_order(sales_order)
	line = materialization._row(order, sales_order_item)
	if not line:
		frappe.throw(_("La línea no pertenece a la Orden de Venta."))
	p = plan(order, line, new_qty, lock=True)
	if p.problem:
		frappe.throw(p.problem)
	text = describe(p)
	with administrator_context():
		(_apply_unknown if p.kind == UNKNOWN else _apply_known)(p, order, line)
	note = _("Cantidad ajustada por {0}: {1} Motivo: {2}").format(frappe.session.user, describe(p), reason)
	_audit("Sales Order", sales_order, note)
	if p.encargo:
		_audit("Encargo", p.encargo, note)
	return {"sales_order": sales_order, "message": text, "encargo": p.encargo}


@frappe.whitelist()
def update_child_qty_rate(parent_doctype, trans_items, parent_doctype_name, child_docname="items"):
	"""Update Items, except on Sales Orders with Encargos (it would recreate every reservation)."""
	if parent_doctype == "Sales Order" and has_encargo(parent_doctype_name):
		frappe.throw(
			_("Esta Orden de Venta tiene Encargos: usa \"Ajustar cantidad\". Para agregar productos o cambiar precios, crea una nueva OV.")
		)
	from erpnext.controllers.accounts_controller import update_child_qty_rate as standard

	return standard(parent_doctype, trans_items, parent_doctype_name, child_docname)
