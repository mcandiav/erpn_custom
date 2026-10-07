"""Spec 020 §14, §15, §19: commercial supply actions on an Encargo.

- Asignar stock a demanda: free stock satisfies demand still without source (no new receipt).
- Liberar compromiso: a committed source stops consuming the demand, with reason and audit.
- Regularización: units that entered as normal stock because of the pre-020 defect.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.chile.elevation import administrator_context
from erpn_custom.encargo import demand, inventory, reception

COMMERCIAL_ROLES = ("ComercialFRA", "System Manager")
ADMIN_ROLE = "System Manager"
REASON_MAX = 1000
LOCK_FIELDS = [
	"name",
	"creation",
	"status",
	"source_type",
	"expected_item",
	"requested_qty",
	"sales_order",
	"sales_order_item",
	"customer",
]


def _require(roles):
	if not set(roles) & set(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def clean_reason(value):
	return (value or "").strip()[:REASON_MAX]


def whole_qty(value):
	qty = flt(value)
	if qty <= 0 or qty != int(qty):
		frappe.throw(_("La cantidad debe ser un número entero mayor que 0."))
	return int(qty)


def older_demand(rows, encargo):
	"""The first Encargo (FIFO by creation, name) before `encargo` that still needs a source."""
	ordered = demand.oldest_first(rows)
	for row in ordered:
		if row.get("name") == encargo:
			return None
		if flt(row.get("pending_supply_qty")) > 0:
			return row.get("name")
	return None


def release_amount(event, arrived):
	"""How much of the event a release takes out of the demand; arrived units are returned one by one."""
	source = event.get("source_type")
	if source == demand.DIRECT:
		return 0
	if source == demand.SHOPPER:
		return demand.in_transit_qty(event, arrived)
	return demand.active_qty(event)


def regularization_candidates(units, enc, limit):
	"""Units that should have been set aside for this demand (Spec 020 §19), oldest first."""
	created = str(enc.get("creation") or "")
	chosen = [
		u
		for u in sorted(units, key=lambda u: (str(u.get("received_on") or ""), u.get("name") or ""))
		if u.get("item") == enc.get("expected_item") and str(u.get("received_on") or "") >= created
	]
	return chosen[: max(int(flt(limit)), 0)]


def _audit(encargo, text):
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Encargo",
			"reference_name": encargo,
			"content": text,
		}
	).insert(ignore_permissions=True)


def _lock_known(encargo):
	row = demand.lock_encargo(encargo, LOCK_FIELDS)
	if not row or row.status != "Open":
		frappe.throw(_("El Encargo no está abierto."))
	if row.source_type != "KNOWN_ITEM" or not row.expected_item:
		frappe.throw(_("Solo aplica a Encargos de producto conocido (KNOWN_ITEM)."))
	return row


def _locked_totals(row):
	events = demand.locked_events(row.name)
	units = demand.locked_units(row.name)
	return events, demand.summarize(row.requested_qty, events, units)


def _open_known_demand(item_code):
	return frappe.get_all(
		"Encargo",
		filters={"status": "Open", "source_type": "KNOWN_ITEM", "expected_item": item_code},
		fields=["name", "creation", "pending_supply_qty"],
	)


def _available(item_code, warehouse):
	from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import get_available_qty_to_reserve

	return flt(get_available_qty_to_reserve(item_code, warehouse))


@frappe.whitelist()
def propose_stock_allocation(encargo):
	"""Free stock per warehouse and the FIFO demand the backend would serve first."""
	_require(COMMERCIAL_ROLES)
	row = frappe.db.get_value("Encargo", encargo, LOCK_FIELDS + ["pending_supply_qty"], as_dict=True)
	if not row or row.source_type != "KNOWN_ITEM" or not row.expected_item:
		frappe.throw(_("Solo aplica a Encargos de producto conocido (KNOWN_ITEM)."))
	warehouses = []
	for wh in frappe.get_all(
		"Bin", filters={"item_code": row.expected_item, "actual_qty": (">", 0)}, pluck="warehouse"
	):
		if wh == inventory.ENCARGO_WAREHOUSE:
			continue
		available = _available(row.expected_item, wh)
		if available >= 1:
			warehouses.append({"warehouse": wh, "available": available})
	return {
		"encargo": encargo,
		"item": row.expected_item,
		"pending_supply_qty": flt(row.pending_supply_qty),
		"fifo_encargo": older_demand(_open_known_demand(row.expected_item), encargo) or encargo,
		"warehouses": warehouses,
	}


@frappe.whitelist(methods=["POST"])
def allocate_stock(encargo, warehouse, qty=1, reason=None):
	"""One Stock Reservation Entry and one STOCK_REALLOCATION event per unit; no Material Receipt."""
	_require(COMMERCIAL_ROLES)
	user = frappe.session.user
	qty = whole_qty(qty)
	reason = clean_reason(reason)
	row = _lock_known(encargo)
	_events, totals = _locked_totals(row)
	if qty > totals.pending_supply_qty:
		frappe.throw(
			_("Solo quedan {0} unidades sin fuente: una compra Shopper comprometida se libera explícitamente.").format(
				f"{totals.pending_supply_qty:g}"
			)
		)
	older = older_demand(_open_known_demand(row.expected_item), encargo)
	if older:
		if ADMIN_ROLE not in frappe.get_roles() or not reason:
			frappe.throw(
				_("{0} es una demanda más antigua del mismo Item: asigna primero ahí (override System Manager con motivo).").format(
					older
				)
			)
	if warehouse == inventory.ENCARGO_WAREHOUSE or not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(_("Bodega no válida para stock libre."))
	reservations = []
	with administrator_context():
		for _i in range(qty):
			sre, problem = inventory.reserve_unit(row.sales_order, row.sales_order_item, row.expected_item, warehouse)
			if problem:
				frappe.throw(problem)
			reservations.append(sre)
			demand.add_event(
				encargo,
				demand.STOCK,
				demand.RECEIVED,
				1,
				user,
				item=row.expected_item,
				warehouse=warehouse,
				stock_reservation_entry=sre,
				notes=reason or None,
			)
	text = _("Stock asignado a demanda: {0} u. de {1} en {2} por {3}.").format(qty, row.expected_item, warehouse, user)
	if older:
		text += " " + _("Override FIFO System Manager (antes {0}).").format(older)
	if reason:
		text += " " + reason
	_audit(encargo, text)
	totals = demand.reconcile_encargo_supply(encargo)
	return {"encargo": encargo, "reservations": reservations, "pending_supply_qty": totals.pending_supply_qty}


@frappe.whitelist(methods=["POST"])
def release_supply_event(encargo, supply_event, reason=None):
	"""Liberar compromiso (Spec 020 §15): never automatic, always with reason and audit."""
	_require(COMMERCIAL_ROLES)
	user = frappe.session.user
	reason = clean_reason(reason)
	if not reason:
		frappe.throw(_("Indica el motivo."))
	row = demand.lock_encargo(encargo, LOCK_FIELDS)
	if not row:
		frappe.throw(_("Encargo no encontrado."))
	events, totals = _locked_totals(row)
	event = next((e for e in events if e.name == supply_event), None)
	if not event or event.status not in demand.ACTIVE:
		frappe.throw(_("El abastecimiento no está comprometido con esta demanda."))
	amount = release_amount(event, totals.event_received.get(event.name, 0))
	if amount <= 0:
		frappe.throw(
			_("No queda cantidad en tránsito que liberar: las unidades ya recibidas se devuelven a stock una a una.")
		)
	if event.source_type == demand.STOCK and event.stock_reservation_entry:
		with administrator_context():
			inventory.cancel_reservation(event.stock_reservation_entry)
	frappe.db.set_value(
		demand.EVENT,
		event.name,
		{"released_qty": flt(event.released_qty) + amount, "notes": reason},
		update_modified=False,
	)
	_audit(
		encargo,
		_("Compromiso liberado: {0} u. de {1} ({2}) por {3}. {4}").format(
			amount, event.source_type, event.purchase_barcode or event.item or "", user, reason
		),
	)
	totals = demand.reconcile_encargo_supply(encargo)
	return {"encargo": encargo, "released": amount, "pending_supply_qty": totals.pending_supply_qty}


def _regularization_units(row, limit):
	units = frappe.get_all(
		reception.UNIT,
		filters={
			"status": reception.POSTED,
			"destination": reception.STOCK,
			"encargo": ("is", "not set"),
			"supply_event": ("is", "not set"),
			"item": row.expected_item,
			"warehouse": inventory.STOCK_WAREHOUSE,
		},
		fields=["name", "item", "scanned_code", "received_on", "received_by", "stock_entry", "incoming_rate"],
	)
	return regularization_candidates(units, row, limit)


@frappe.whitelist()
def preview_direct_regularization(encargo):
	"""Read-only: which units would be set aside for this demand and what would change."""
	_require((ADMIN_ROLE,))
	row = frappe.db.get_value("Encargo", encargo, LOCK_FIELDS + ["pending_supply_qty"], as_dict=True)
	if not row or row.status != "Open" or row.source_type != "KNOWN_ITEM":
		frappe.throw(_("Solo aplica a Encargos abiertos de producto conocido."))
	units = _regularization_units(row, row.pending_supply_qty)
	return {
		"encargo": encargo,
		"item": row.expected_item,
		"sales_order": row.sales_order,
		"pending_supply_qty": flt(row.pending_supply_qty),
		"available_in_stock": _available(row.expected_item, inventory.STOCK_WAREHOUSE),
		"units": units,
	}


@frappe.whitelist(methods=["POST"])
def apply_direct_regularization(encargo, units):
	"""Per unit: transfer Matriz -> Recepcion Encargos, RECEPTION_DIRECT event, reservation, log."""
	_require((ADMIN_ROLE,))
	user = frappe.session.user
	wanted = [u for u in (frappe.parse_json(units) or []) if u]
	if not wanted:
		frappe.throw(_("Selecciona las unidades a regularizar."))
	row = _lock_known(encargo)
	_events, totals = _locked_totals(row)
	allowed = {u.name for u in _regularization_units(row, totals.pending_supply_qty)}
	invalid = [u for u in wanted if u not in allowed]
	if invalid:
		frappe.throw(_("Unidades no elegibles o fuera del pendiente: {0}. Vuelve a abrir la vista previa.").format(", ".join(invalid)))
	available = _available(row.expected_item, inventory.STOCK_WAREHOUSE)
	if available < len(wanted):
		frappe.throw(
			_("En {0} solo hay {1} unidades libres de {2}: el resto ya está reservado o vendido.").format(
				inventory.STOCK_WAREHOUSE, f"{available:g}", row.expected_item
			)
		)
	enc = reception._lock(encargo)
	results = []
	with administrator_context():
		for name in wanted:
			frappe.db.get_value(reception.UNIT, name, "name", for_update=True)
			doc = frappe.get_doc(reception.UNIT, name)
			transfer = inventory.make_transfer(
				inventory.reception_company(),
				doc.item,
				inventory.STOCK_WAREHOUSE,
				inventory.ENCARGO_WAREHOUSE,
				_("Regularización Spec 020 {0} -> {1}").format(doc.name, encargo),
			)
			event = demand.add_event(
				encargo,
				demand.DIRECT,
				demand.RECEIVED,
				1,
				user,
				item=doc.item,
				reception_unit=doc.name,
				warehouse=inventory.ENCARGO_WAREHOUSE,
				notes=_("Regularización Spec 020 · traslado {0}").format(transfer),
			)
			doc.update(
				{
					"encargo": encargo,
					"sales_order": row.sales_order,
					"sales_order_item": row.sales_order_item,
					"customer": row.customer,
					"destination": reception.ENCARGO,
					"supply_event": event,
					"warehouse": inventory.ENCARGO_WAREHOUSE,
					"message": _("Regularizada a {0} (traslado {1}).").format(encargo, transfer),
				}
			)
			reception._reserve(doc, enc)
			doc.save(ignore_permissions=True)
			frappe.db.set_value(demand.EVENT, event, "stock_reservation_entry", doc.stock_reservation_entry, update_modified=False)
			reception._log(encargo, "RECEIVED", user, scanned_code=doc.scanned_code, notes=_("Regularización {0}").format(doc.name))
			results.append({"unit": doc.name, "transfer": transfer, "reservation": doc.stock_reservation_entry, "note": doc.reservation_note})
	_audit(encargo, _("Regularización Spec 020 por {0}: {1}.").format(user, ", ".join(r["unit"] for r in results)))
	totals = demand.reconcile_encargo_supply(encargo)
	return {"encargo": encargo, "units": results, "pending_supply_qty": totals.pending_supply_qty, "covered_qty": totals.covered_qty}
