import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, strip_html

from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS
from erpn_custom.chile.elevation import administrator_context
from erpn_custom.encargo import barcode_exception, demand, inventory, materialization

RECEPTOR_ROLE = "FRAreceptor"
ALLOWED_ROLES = (RECEPTOR_ROLE, "System Manager")
# The receptor only scans; commercial staff resolve exceptions and return units to stock.
COMMERCIAL_ROLES = ("ComercialFRA", "System Manager")
ADMIN_ROLE = "System Manager"
UNIT = "Recepcion Unidad"
CODE_MAX = 140
NOTES_MAX = 1000
SCAN_EVENT_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

POSTED = "POSTED"
PENDING_CLASSIFICATION = "PENDING_CLASSIFICATION"
PENDING_BARCODE_APPROVAL = "PENDING_BARCODE_APPROVAL"
PENDING_COST = "PENDING_COST"
PENDING_CONFIGURATION = "PENDING_CONFIGURATION"
RETURNED = "RETURNED_TO_STOCK"
# Mismatches wait for the commercial approval of Spec 017 (barcode_exception.approve / reject).
RESOLVABLE = (PENDING_CLASSIFICATION, PENDING_COST, PENDING_CONFIGURATION)
ENCARGO = "ENCARGO"
STOCK = "STOCK"
# Reception marks written before Spec 018, without inventory movement.
PRE_018_RECEIVED = ("RECEIVED", "RESOLVED_TO_ENC", "RESOLVED_TO_STOCK")

CARD_FIELDS = [
	"name",
	"sales_order",
	"customer",
	"description",
	"brand",
	"purchase_barcode",
	"purchased_on",
	"purchase_supplier",
	"proposed_supplier_name",
	"requested_qty",
	"received_qty",
	"pending_receive_qty",
	"pending_supply_qty",
	"reception_status",
	"received_on",
	"received_by",
]
LOCK_FIELDS = [
	"name",
	"creation",
	"status",
	"purchase_status",
	"reception_status",
	"purchase_barcode",
	"purchased_on",
	"purchase_price",
	"purchase_currency",
	"requested_qty",
	"received_qty",
	"source_type",
	"expected_item",
	"resolved_item",
	"sales_order",
	"sales_order_item",
	"customer",
	"barcode_exception_status",
]
ITEM_SOURCE_FIELDS = ["description", "brand", "item_group", "custom_departamento", *ATTRIBUTE_FIELDS.values()]
UNIT_FIELDS = [
	"name",
	"status",
	"destination",
	"scanned_code",
	"encargo",
	"sales_order",
	"customer",
	"item",
	"item_name",
	"warehouse",
	"stock_entry",
	"stock_reservation_entry",
	"reservation_note",
	"incoming_rate",
	"exchange_rate",
	"message",
	"received_on",
	"received_by",
	"is_migration",
	"supply_event",
	"materialization_status",
	"materialized_row",
	"materialization_message",
]
COMMERCIAL_VIEWS = {
	"apartados": {"status": POSTED, "destination": ENCARGO},
	"clasificacion": {"status": PENDING_CLASSIFICATION},
	"valorizacion": {"status": ("in", [PENDING_COST, PENDING_CONFIGURATION])},
	"vincular": {
		"status": POSTED,
		"destination": ENCARGO,
		"materialization_status": ("in", list(materialization.RETRYABLE)),
	},
}


def is_receptor(roles):
	return bool(set(ALLOWED_ROLES) & set(roles))


def is_commercial(roles):
	return bool(set(COMMERCIAL_ROLES) & set(roles))


def is_admin(roles):
	return ADMIN_ROLE in roles


def _require(allowed):
	if not allowed(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def clean_code(value):
	"""The scanned value is opaque (EAN, UPC, QR, URL...): only the scanner's edge spaces are removed."""
	return (value or "").strip()[:CODE_MAX]


def clean_notes(value):
	return (value or "").strip()[:NOTES_MAX]


def clean_scan_event_id(value):
	"""Each read carries its own id from the phone; the barcode is shared by identical units."""
	value = (value or "").strip()
	if not SCAN_EVENT_ID.match(value):
		frappe.throw(_("Lectura sin identificador: recarga la página de recepción."))
	return value


def migration_scan_event_id(encargo):
	return f"MIG-{encargo}"


def migration_destination(reception_status):
	return STOCK if reception_status == "RESOLVED_TO_STOCK" else ENCARGO


def screen(status, destination, has_encargo, materialization_status=None, encargo=None):
	"""(title, kind) shown to the receptor; kind picks the colour."""
	if status == POSTED and destination == ENCARGO and materialization_status == materialization.ERROR:
		# The unit is in inventory and still set aside; only the Sales Order link failed (Spec 019 §16).
		return f"APARTAR - {encargo} - PENDIENTE DE VINCULAR A OV", "warning"
	suffix = f" - {encargo}" if encargo else ""
	if status == POSTED:
		return (f"APARTAR{suffix}", "encargo") if destination == ENCARGO else ("STOCK NORMAL", "stock")
	if status == PENDING_CLASSIFICATION:
		if has_encargo:
			return f"APARTAR - REQUIERE CLASIFICACION{suffix}", "warning"
		return "STOCK NORMAL - REQUIERE CLASIFICACION", "warning"
	if status == PENDING_BARCODE_APPROVAL:
		return f"APARTAR - REQUIERE COMERCIAL{suffix}", "warning"
	if status in (PENDING_COST, PENDING_CONFIGURATION):
		return "RECIBIDO - PENDIENTE DE VALORIZACION", "warning"
	return "DEVUELTO A STOCK", "stock"


def exact_matches(rows, code, field="purchase_barcode"):
	"""The database collation ignores case; short QR links do not, so the final comparison is exact."""
	return [row for row in rows if (row.get(field) or "") == code]


def encargo_matches(row, code, barcode_items, event_barcodes=()):
	"""Compatible demand: a purchase of this exact code, or a known Item that owns the code."""
	if code in event_barcodes:
		return True
	return row.get("source_type") == "KNOWN_ITEM" and row.get("expected_item") in barcode_items


def oldest_first(rows):
	"""Each unit goes to the oldest compatible demand: Encargo creation, then name (Spec 020 §8)."""
	return demand.oldest_first(rows)


def is_receivable(row):
	"""Spec 020 §8: a purchase is not required; the demand only has to be open."""
	return bool(row and row.get("status") == "Open")


def has_capacity(row, assigned_units):
	return cint(assigned_units) < flt(row.get("requested_qty"))


def still_waits_for_unit(row):
	"""A pending unit resolved later still belongs to its Encargo unless sales closed it meanwhile."""
	return is_receivable(row)


def pick_source(row, events, arrived, pending_supply, code, barcode_items, same_item_events=()):
	"""(kind, event) for one scanned unit: 'event' = a purchase in transit, 'direct' = new direct reception.

	1. a purchase in transit of this exact code;
	2. known Item: a purchase in transit of the same Item that is not waiting for a barcode decision;
	3. known Item with demand still without source: direct reception (no Shopper purchase needed);
	4. otherwise the unit is not committed to this demand (Spec 020 §8, §15).
	"""
	in_transit = [
		e
		for e in sorted(events, key=lambda e: e.get("idx") or 0)
		if e.get("source_type") == demand.SHOPPER and demand.in_transit_qty(e, arrived.get(e.get("name"), 0)) > 0
	]
	for event in in_transit:
		if (event.get("purchase_barcode") or "") == code:
			return "event", event
	if row.get("source_type") != "KNOWN_ITEM" or row.get("expected_item") not in barcode_items:
		return None, None
	for event in in_transit:
		if event.get("name") in same_item_events and event.get("barcode_exception_status") != barcode_exception.PENDING_APPROVAL:
			return "event", event
	if flt(pending_supply) > 0:
		return "direct", None
	return None, None


def return_decision(row):
	"""'return' for a unit set aside for a customer; 'already_done' when it is already stock."""
	if not row:
		frappe.throw(_("Unidad de recepción no encontrada."))
	if row.get("status") == RETURNED:
		return "already_done"
	if row.get("status") != POSTED or row.get("destination") != ENCARGO:
		frappe.throw(_("Solo se devuelven a stock unidades apartadas para un Encargo."))
	return "return"


def _lock(encargo):
	return frappe.db.get_value("Encargo", encargo, LOCK_FIELDS, as_dict=True, for_update=True)


def _log(encargo, action, user, **values):
	count = frappe.db.count("Encargo Reception Event", {"parent": encargo})
	frappe.get_doc(
		{
			"doctype": "Encargo Reception Event",
			"name": frappe.generate_hash(length=10),
			"parent": encargo,
			"parenttype": "Encargo",
			"parentfield": "reception_events",
			"idx": count + 1,
			"action": action,
			"event_on": now_datetime(),
			"user": user,
			**values,
		}
	).db_insert()


def _card(encargo):
	return frappe.db.get_value("Encargo", encargo, CARD_FIELDS, as_dict=True)


def _candidates(code, barcode_items):
	"""Open demand compatible with the code, oldest first; a purchase is not required (Spec 020 §8)."""
	# Rejected or released purchases no longer belong to their Encargo (Spec 017 §8.6, Spec 020 §15).
	events = frappe.get_all(
		demand.EVENT,
		filters={
			"parenttype": "Encargo",
			"source_type": demand.SHOPPER,
			"status": demand.COMMITTED,
			"purchase_barcode": code,
		},
		fields=["parent", "purchase_barcode"],
	)
	by_purchase = {}
	for event in exact_matches(events, code):
		by_purchase.setdefault(event.parent, set()).add(event.purchase_barcode)
	fields = ["name", "creation", "source_type", "expected_item"]
	rows = []
	if by_purchase:
		rows += frappe.get_all("Encargo", filters={"status": "Open", "name": ("in", list(by_purchase))}, fields=fields)
	if barcode_items:
		rows += frappe.get_all(
			"Encargo",
			filters={"status": "Open", "source_type": "KNOWN_ITEM", "expected_item": ("in", barcode_items)},
			fields=fields,
		)
	unique = {
		row.name: row for row in rows if encargo_matches(row, code, barcode_items, by_purchase.get(row.name, ()))
	}
	return oldest_first(unique.values())


def _same_item_events(row, events):
	"""Purchases whose code also belongs to the expected Item (another barcode of the same product)."""
	if row.get("source_type") != "KNOWN_ITEM":
		return set()
	return {
		e.name
		for e in events
		if e.get("purchase_barcode") and row.expected_item in inventory.items_for_barcode(e.purchase_barcode)
	}


def _assign_encargo(code, barcode_items):
	"""(Encargo, kind, event) under lock, or (None, None, None) for normal stock."""
	for candidate in _candidates(code, barcode_items):
		# Another receptor may have taken the last unit between the search and the lock.
		row = _lock(candidate.name)
		if not is_receivable(row):
			continue
		events = demand.locked_events(row.name)
		units = demand.locked_units(row.name)
		if not has_capacity(row, sum(1 for unit in units if demand.is_live_unit(unit))):
			continue
		totals = demand.summarize(row.requested_qty, events, units)
		kind, event = pick_source(
			row,
			events,
			totals.event_received,
			totals.pending_supply_qty,
			code,
			barcode_items,
			_same_item_events(row, events),
		)
		if kind:
			return row, kind, event
	return None, None, None


def _new_unit(code, scan_event_id, user, received_on=None, is_migration=0):
	return frappe.get_doc(
		{
			"doctype": UNIT,
			"scan_event_id": scan_event_id,
			"scanned_code": code,
			"status": PENDING_CLASSIFICATION,
			"destination": STOCK,
			"received_on": received_on or now_datetime(),
			"received_by": user,
			"is_migration": is_migration,
		}
	)


def _link_encargo(unit, row, destination=ENCARGO, event=None):
	"""The cost comes from the purchase the unit satisfies; a direct reception has none (Item cost)."""
	source = event if event is not None else row
	unit.update(
		{
			"encargo": row.name,
			"sales_order": row.sales_order,
			"sales_order_item": row.sales_order_item,
			"customer": row.customer,
			"destination": destination,
			"supply_event": event.name if event is not None else None,
			"purchase_currency": source.get("purchase_currency") or inventory.PURCHASE_CURRENCY,
			"purchase_price": flt(source.get("purchase_price")),
			"purchased_on": source.get("purchased_on"),
		}
	)


def _resolve_item(unit, enc, barcode_items):
	"""(pending_status, item, message): pending_status None means the Item is known."""
	code = unit.scanned_code
	barcode_item = barcode_items[0] if barcode_items else None
	if not enc:
		if barcode_item:
			return None, barcode_item, None
		return PENDING_CLASSIFICATION, None, _("El código no corresponde a ningún Item ni Encargo pendiente.")
	if enc.source_type == "KNOWN_ITEM":
		if enc.expected_item in barcode_items:
			barcode_item = enc.expected_item
		# Spec 020 §13: the exception belongs to the purchase event of this unit.
		event_status = (
			frappe.db.get_value(demand.EVENT, unit.supply_event, "barcode_exception_status") if unit.supply_event else None
		)
		if event_status == barcode_exception.PENDING_APPROVAL:
			decision = "mismatch"
		else:
			# Purchases before Spec 017 still adopt the first code here (§9.2).
			decision = inventory.known_item_decision(
				enc.expected_item, barcode_item, inventory.item_has_barcodes(enc.expected_item)
			)
		if decision == "mismatch":
			if not unit.supply_event:
				return (
					PENDING_CLASSIFICATION,
					None,
					_("El código no corresponde al Item esperado {0} y la unidad no tiene compra asociada.").format(
						enc.expected_item
					),
				)
			if event_status != barcode_exception.PENDING_APPROVAL:
				barcode_exception.open_exception(enc.name, unit.supply_event)
			return (
				PENDING_BARCODE_APPROVAL,
				None,
				_("El código no corresponde al Item esperado {0}: requiere aprobación comercial.").format(
					enc.expected_item
				),
			)
		if decision == "adopt":
			inventory.add_barcode(enc.expected_item, code)
		return None, enc.expected_item, None
	item = enc.resolved_item or barcode_item
	if item and barcode_item and barcode_item != item:
		return (
			PENDING_BARCODE_APPROVAL,
			None,
			_("El código pertenece al Item {0} y el Encargo está resuelto con {1}.").format(barcode_item, item),
		)
	if item and not barcode_item:
		inventory.add_barcode(item, code)
	if not item:
		values = frappe.db.get_value("Encargo", enc.name, ITEM_SOURCE_FIELDS, as_dict=True)
		item, problem = inventory.create_item_from_encargo(values, code)
		if problem:
			return PENDING_CLASSIFICATION, None, problem
		unit.item_created = 1
	if enc.resolved_item != item:
		frappe.db.set_value("Encargo", enc.name, "resolved_item", item, update_modified=False)
		enc.resolved_item = item
	return None, item, None


def _incoming_rate(unit, company, warehouse):
	"""(rate, problem). Shopper units: price x rate of the purchase date; others: known Item cost."""
	# A unit detached from a rejected Encargo keeps the price the shopper paid.
	if flt(unit.purchase_price) > 0:
		company_currency = frappe.get_cached_value("Company", company, "default_currency")
		currency = unit.purchase_currency or inventory.PURCHASE_CURRENCY
		rate, source = inventory.exchange_rate(currency, company_currency, unit.purchased_on or now_datetime())
		unit.exchange_rate = rate
		unit.exchange_rate_source = source or ""
		if not rate:
			return 0, _("Sin tipo de cambio {0} -> {1} para el {2} ni tasa de respaldo.").format(
				currency, company_currency, getdate(unit.purchased_on or now_datetime())
			)
		unit.rate_source = "SHOPPER"
		return flt(unit.purchase_price) * rate, None
	rate, source = inventory.stock_rate(unit.item, warehouse)
	if not rate:
		return 0, _("El Item {0} no tiene costo conocido (valorización ni última entrada).").format(unit.item)
	unit.rate_source = source
	return rate, None


def _count_received(unit, enc):
	"""Quantities are recomputed by demand.reconcile_encargo_supply once the unit is saved."""
	if unit.is_migration:
		# _advance runs as Administrator; the owner is the System Manager who ran the regularization.
		_log(enc.name, "RECEIVED", unit.owner, scanned_code=unit.scanned_code, notes=_("Regularización {0}").format(unit.name))
	else:
		_log(enc.name, "RECEIVED", unit.received_by, scanned_code=unit.scanned_code)


def _reserve(unit, enc):
	if enc.source_type == "KNOWN_ITEM" and unit.item == enc.expected_item:
		unit.stock_reservation_entry, unit.reservation_note = inventory.reserve_unit(
			unit.sales_order, unit.sales_order_item, unit.item, unit.warehouse
		)
	elif materialization.applies(enc):
		unit.materialization_status = materialization.PENDING
		materialization.materialize(unit)
	else:
		unit.reservation_note = _(
			"Apartado por bodega y Encargo: la línea de la Orden de Venta aún no tiene el Item real."
		)


def _advance(unit, barcode_items=None):
	"""Moves a unit as far as the data allows: Item, configuration, cost, Material Receipt, reservation."""
	if barcode_items is None:
		barcode_items = inventory.items_for_barcode(unit.scanned_code)
	enc = _lock(unit.encargo) if unit.encargo else None
	if not unit.item:
		status, item, message = _resolve_item(unit, enc, barcode_items)
		if status:
			unit.status, unit.message = status, message
			return
		unit.item = item
	account = inventory.clearing_account()
	if not account:
		unit.status = PENDING_CONFIGURATION
		unit.message = _("Falta la cuenta transitoria en Configuracion Recepcion FRA.")
		return
	company = inventory.reception_company()
	warehouse = inventory.ENCARGO_WAREHOUSE if unit.destination == ENCARGO else inventory.STOCK_WAREHOUSE
	rate, problem = _incoming_rate(unit, company, warehouse)
	if problem:
		unit.status, unit.message = PENDING_COST, problem
		return
	remarks = _("Recepción Chile {0} · código {1}").format(unit.name, unit.scanned_code)
	if unit.encargo:
		remarks += " · " + unit.encargo
	frappe.db.savepoint("reception_receipt")
	try:
		unit.stock_entry = inventory.make_receipt(company, unit.item, warehouse, rate, account, remarks)
	except Exception as e:
		frappe.db.rollback(save_point="reception_receipt")
		frappe.clear_messages()
		unit.status = PENDING_COST
		unit.message = _("No se pudo ingresar al inventario: {0}").format(strip_html(str(e)))[:500]
		return
	unit.update({"warehouse": warehouse, "incoming_rate": rate, "status": POSTED, "message": None})
	if unit.destination == ENCARGO:
		_count_received(unit, enc)
		_reserve(unit, enc)


def unit_result(name, duplicate=False):
	unit = frappe.db.get_value(UNIT, name, UNIT_FIELDS, as_dict=True)
	title, kind = screen(
		unit.status, unit.destination, bool(unit.encargo), unit.materialization_status, unit.encargo
	)
	encargo = _card(unit.encargo) if unit.encargo else None
	return {
		"unit": unit.name,
		"status": unit.status,
		"destination": unit.destination,
		"screen": title,
		"kind": kind,
		"code": unit.scanned_code,
		"encargo": encargo,
		"pending_receive_qty": flt(encargo.pending_receive_qty) if encargo else 0,
		"item": unit.item,
		"item_name": unit.item_name,
		"message": unit.message or unit.materialization_message,
		"duplicate": int(bool(duplicate)),
	}


def _unit_by_scan(scan_event_id):
	return frappe.db.get_value(UNIT, {"scan_event_id": scan_event_id}, "name")


@frappe.whitelist(methods=["POST"])
def receive_scan(code, scan_event_id=None):
	"""One scan = one unit (Spec 018): Encargo FIFO, Item, Material Receipt; a repeated scan_event_id is a no-op."""
	_require(is_receptor)
	code = clean_code(code)
	if not code:
		frappe.throw(_("Escanea o escribe un código."))
	scan_event_id = clean_scan_event_id(scan_event_id)
	existing = _unit_by_scan(scan_event_id)
	if existing:
		return unit_result(existing, duplicate=True)
	barcode_items = inventory.items_for_barcode(code)
	user = frappe.session.user
	unit = _new_unit(code, scan_event_id, user)
	row, kind, event = _assign_encargo(code, barcode_items)
	if kind == "direct":
		# Spec 020 §8: a compatible unit satisfies demand without a prior Shopper purchase.
		event = frappe._dict(
			name=demand.add_event(
				row.name, demand.DIRECT, demand.RECEIVED, 1, user, item=row.expected_item, notes=_("Escaneo {0}").format(code)
			)
		)
	if row:
		_link_encargo(unit, row, ENCARGO, event)
	try:
		unit.insert(ignore_permissions=True)
	except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
		# The same read arrived twice at once: the first one wins.
		frappe.db.rollback()
		return unit_result(_unit_by_scan(scan_event_id), duplicate=True)
	if kind == "direct":
		frappe.db.set_value(demand.EVENT, event.name, "reception_unit", unit.name, update_modified=False)
	with administrator_context():
		_advance(unit, barcode_items)
		_save(unit)
	return unit_result(unit.name)


def _save(unit, previous_encargo=None):
	"""Save the unit, then recompute the demand it belongs (or belonged) to from real data."""
	unit.save(ignore_permissions=True)
	for encargo in {unit.encargo, previous_encargo} - {None, ""}:
		demand.reconcile_encargo_supply(encargo)


@frappe.whitelist()
def list_reception(view="pending", search=None, limit=100):
	"""Receptor lists: Encargos with purchased units still in transit, and units scanned today."""
	_require(is_receptor)
	limit = min(cint(limit) or 100, 500)
	text = (search or "").strip()
	like = f"%{text}%"
	if view == "today":
		or_filters = (
			{"scanned_code": ("like", like), "encargo": ("like", like), "customer": ("like", like), "item": ("like", like)}
			if text
			else None
		)
		rows = frappe.get_all(
			UNIT,
			filters={"received_on": (">=", getdate()), "is_migration": 0},
			or_filters=or_filters,
			fields=[
				"name",
				"status",
				"destination",
				"scanned_code",
				"encargo",
				"customer",
				"item_name",
				"received_on",
				"received_by",
				"materialization_status",
			],
			order_by="received_on desc",
			limit_page_length=limit,
		)
		for row in rows:
			row.screen = screen(row.status, row.destination, bool(row.encargo), row.materialization_status, row.encargo)[0]
		return rows
	or_filters = None
	if text:
		or_filters = {
			"name": ("like", like),
			"sales_order": ("like", like),
			"customer": ("like", like),
			"brand": ("like", like),
			"description": ("like", like),
		}
	return frappe.get_all(
		"Encargo",
		filters={"status": "Open", "pending_receive_qty": (">", 0)},
		or_filters=or_filters,
		fields=CARD_FIELDS,
		order_by="creation asc, name asc",
		limit_page_length=limit,
	)


@frappe.whitelist()
def list_units(view="apartados", search=None, limit=200):
	"""ComercialFRA queues: units set aside, and the exceptions the receptor could not close."""
	_require(is_commercial)
	if view not in COMMERCIAL_VIEWS:
		frappe.throw(_("Vista desconocida."))
	text = (search or "").strip()
	or_filters = None
	if text:
		like = f"%{text}%"
		or_filters = {
			"scanned_code": ("like", like),
			"encargo": ("like", like),
			"sales_order": ("like", like),
			"customer": ("like", like),
			"item": ("like", like),
		}
	rows = frappe.get_all(
		UNIT,
		filters=COMMERCIAL_VIEWS[view],
		or_filters=or_filters,
		fields=UNIT_FIELDS,
		order_by="received_on desc" if view == "apartados" else "received_on asc",
		limit_page_length=min(cint(limit) or 200, 500),
	)
	return {"rows": rows, "configured": bool(inventory.clearing_account())}


def _apply_chosen_item(unit, enc, item):
	if not frappe.db.exists("Item", {"name": item, "disabled": 0, "is_stock_item": 1}):
		frappe.throw(_("El Item {0} no existe, está deshabilitado o no maneja stock.").format(item))
	if enc and enc.source_type == "KNOWN_ITEM":
		frappe.throw(_("El Item de un Encargo de producto conocido no se cambia en la recepción."))
	owners = inventory.items_for_barcode(unit.scanned_code)
	if owners and item not in owners:
		frappe.throw(_("El código {0} ya pertenece al Item {1}.").format(unit.scanned_code, owners[0]))
	if not owners:
		inventory.add_barcode(item, unit.scanned_code)
	unit.item = item
	if enc and enc.resolved_item != item:
		frappe.db.set_value("Encargo", enc.name, "resolved_item", item, update_modified=False)


@frappe.whitelist(methods=["POST"])
def resolve_unit(unit, item=None):
	"""Resolver / Reintentar valorización: completes a pending unit with the same scan_event_id."""
	_require(is_commercial)
	user = frappe.session.user
	status = frappe.db.get_value(UNIT, unit, "status", for_update=True)
	if status not in RESOLVABLE:
		frappe.throw(_("La unidad {0} no está pendiente de clasificación ni de valorización.").format(unit))
	item = (item or "").strip() or None
	with administrator_context():
		doc = frappe.get_doc(UNIT, unit)
		enc = _lock(doc.encargo) if doc.encargo else None
		if enc and doc.destination == ENCARGO and not still_waits_for_unit(enc):
			doc.destination = STOCK
		if item:
			_apply_chosen_item(doc, enc, item)
		_advance(doc)
		doc.resolved_on = now_datetime()
		doc.resolved_by = user
		_save(doc)
	return unit_result(doc.name)


@frappe.whitelist(methods=["POST"])
def retry_materialization(unit):
	"""Pendientes de vincular a OV: the same deterministic service; ComercialFRA never edits quantities."""
	_require(is_commercial)
	user = frappe.session.user
	row = frappe.db.get_value(
		UNIT, unit, ["status", "destination", "materialization_status"], as_dict=True, for_update=True
	)
	if (
		not row
		or row.status != POSTED
		or row.destination != ENCARGO
		or row.materialization_status not in materialization.RETRYABLE
	):
		frappe.throw(_("La unidad {0} no está pendiente de vincular a la Orden de Venta.").format(unit))
	with administrator_context():
		doc = frappe.get_doc(UNIT, unit)
		materialization.materialize(doc, user)
		doc.save(ignore_permissions=True)
	return unit_result(doc.name)


def detach_rejected(unit, user):
	"""The unit stops belonging to the rejected Encargo; it enters as normal stock (Spec 017 §14.2)."""
	encargo = unit.encargo
	unit.update(
		{
			"rejected_encargo": encargo,
			"encargo": None,
			"sales_order": None,
			"sales_order_item": None,
			"customer": None,
			"destination": STOCK,
			"item": None,
			"message": None,
		}
	)
	_log(encargo, "BARCODE_REJECTED", user, scanned_code=unit.scanned_code, notes=unit.name)


def resume_after_barcode_decision(encargo, approved, supply_event=None):
	"""Same Recepcion Unidad, no new scan: approval retries it, rejection sends it to stock.

	Spec 020 §13: only the units of the decided purchase event move.
	"""
	user = frappe.session.user
	results = []
	filters = {"encargo": encargo, "status": PENDING_BARCODE_APPROVAL}
	if supply_event:
		filters["supply_event"] = supply_event
	for name in frappe.get_all(UNIT, filters=filters, pluck="name", order_by="received_on asc"):
		with administrator_context():
			doc = frappe.get_doc(UNIT, name)
			if not approved:
				detach_rejected(doc, user)
			_advance(doc)
			doc.resolved_on = now_datetime()
			doc.resolved_by = user
			doc.save(ignore_permissions=True)
		result = unit_result(doc.name)
		results.append({"unit": doc.name, "screen": result["screen"], "message": result["message"]})
	demand.reconcile_encargo_supply(encargo)
	return results


@frappe.whitelist(methods=["POST"])
def return_unit(unit, notes=None):
	"""DEVOLVER A STOCK: releases the reservation and moves the unit to Matriz; sales handles the order line."""
	_require(is_commercial)
	user = frappe.session.user
	notes = clean_notes(notes)
	if not notes:
		frappe.throw(_("Indica el motivo de la devolución a stock."))
	encargo = frappe.db.get_value(UNIT, unit, "encargo")
	if encargo:
		# Same lock order as reception: Encargo first, then its units.
		demand.lock_encargo(encargo, ["name"])
	row = frappe.db.get_value(UNIT, unit, ["name", "status", "destination"], as_dict=True, for_update=True)
	if return_decision(row) == "already_done":
		return unit_result(unit)
	with administrator_context():
		doc = frappe.get_doc(UNIT, unit)
		inventory.cancel_reservation(doc.stock_reservation_entry)
		materialization.reverse(doc, user, notes)
		transfer = inventory.make_transfer(
			inventory.reception_company(),
			doc.item,
			doc.warehouse,
			inventory.STOCK_WAREHOUSE,
			_("Devolver a stock {0}: {1}").format(doc.name, notes),
		)
		doc.update(
			{
				"status": RETURNED,
				"return_transfer": transfer,
				"warehouse": inventory.STOCK_WAREHOUSE,
				"returned_on": now_datetime(),
				"returned_by": user,
				"return_reason": notes,
			}
		)
		doc.save(ignore_permissions=True)
		if doc.encargo:
			release_unit_source(doc.encargo, doc.supply_event)
			_log(doc.encargo, "RETURNED_TO_STOCK", user, scanned_code=doc.scanned_code, notes=notes)
			demand.reconcile_encargo_supply(doc.encargo)
	return unit_result(unit)


def release_unit_source(encargo, supply_event):
	"""The returned unit stops consuming its source; the demand reopens unless covered otherwise."""
	if not supply_event:
		return
	released = frappe.db.get_value(demand.EVENT, supply_event, "released_qty", for_update=True)
	if released is None:
		return
	frappe.db.set_value(demand.EVENT, supply_event, "released_qty", flt(released) + 1, update_modified=False)


@frappe.whitelist(methods=["POST"])
def regularize_previous_receptions():
	"""Spec 018 §18: receptions marked before this Spec go through the same service, one unit each."""
	_require(is_admin)
	if not inventory.clearing_account():
		frappe.throw(_("Configura la cuenta transitoria antes de regularizar."))
	rows = frappe.get_all(
		"Encargo",
		filters={"reception_status": ("in", list(PRE_018_RECEIVED)), "received_on": ("is", "set")},
		fields=[*LOCK_FIELDS, "received_on", "received_by"],
		order_by="received_on asc",
	)
	results = []
	for row in rows:
		# Spec 020: Encargos with supply events are already reconciled by the v0_0_43 migration.
		if frappe.db.exists(UNIT, {"encargo": row.name}) or frappe.db.exists(demand.EVENT, {"parent": row.name}):
			continue
		if not row.purchase_barcode:
			results.append({"encargo": row.name, "unit": "", "screen": _("SIN CÓDIGO"), "message": _("El Encargo no tiene código comprado.")})
			continue
		unit = _new_unit(
			row.purchase_barcode,
			migration_scan_event_id(row.name),
			row.received_by or frappe.session.user,
			row.received_on,
			is_migration=1,
		)
		_link_encargo(unit, row, migration_destination(row.reception_status))
		frappe.db.savepoint("reception_regularize")
		try:
			unit.insert(ignore_permissions=True)
			with administrator_context():
				_advance(unit)
				_save(unit)
		except Exception as e:
			frappe.db.rollback(save_point="reception_regularize")
			frappe.clear_messages()
			results.append({"encargo": row.name, "unit": "", "screen": _("ERROR"), "message": str(e)[:300]})
			continue
		result = unit_result(unit.name)
		results.append({"encargo": row.name, "unit": unit.name, "screen": result["screen"], "message": result["message"]})
	return results
