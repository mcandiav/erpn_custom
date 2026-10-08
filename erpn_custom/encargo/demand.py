"""Spec 020: an Encargo is demand; its quantities are derived from supply events and reception units."""

import frappe
from frappe.utils import flt, now_datetime

EVENT = "Encargo Supply Event"
UNIT = "Recepcion Unidad"

SHOPPER = "SHOPPER_PURCHASE"
DIRECT = "RECEPTION_DIRECT"
STOCK = "STOCK_REALLOCATION"
# Receptions marked before Spec 018 without a Recepcion Unidad: already covered, nothing to scan.
MIGRATION = "MIGRATION"
# Sources whose units still have to travel to Chile.
IN_TRANSIT_SOURCES = (SHOPPER,)
PURCHASE_SOURCES = (SHOPPER, MIGRATION)

COMMITTED = "COMMITTED"
RECEIVED = "RECEIVED"
REJECTED = "REJECTED"
CANCELLED = "CANCELLED"
RESOLVED_TO_STOCK = "RESOLVED_TO_STOCK"
ACTIVE = (COMMITTED, RECEIVED)

PENDING_APPROVAL = "PENDING_APPROVAL"
POSTED = "POSTED"
RETURNED = "RETURNED_TO_STOCK"
ENCARGO_DESTINATION = "ENCARGO"
LIVE_RECEPTION = ("PENDING", "RECEIVED")

EVENT_FIELDS = [
	"name",
	"idx",
	"source_type",
	"status",
	"qty",
	"received_qty",
	"released_qty",
	"event_on",
	"shopper_user",
	"supplier",
	"proposed_supplier_name",
	"purchase_barcode",
	"purchase_price",
	"purchase_currency",
	"purchased_on",
	"purchase_product_image",
	"purchase_label_image",
	"barcode_exception_status",
	"expected_barcode",
	"item",
	"warehouse",
	"stock_reservation_entry",
	"reception_unit",
	"request_id",
]
UNIT_FIELDS = ["name", "status", "destination", "supply_event", "warehouse", "stock_reservation_entry"]
ENCARGO_FIELDS = [
	"name",
	"status",
	"source_type",
	"sales_order_item",
	"requested_qty",
	"received_qty",
	"purchase_status",
	"reception_status",
	"barcode_exception_status",
]


def active_qty(event):
	"""Quantity of the event that still consumes demand."""
	if event.get("status") not in ACTIVE:
		return 0
	return max(flt(event.get("qty")) - flt(event.get("released_qty")), 0)


def in_transit_qty(event, arrived):
	if event.get("source_type") not in IN_TRANSIT_SOURCES:
		return 0
	return max(active_qty(event) - flt(arrived), 0)


def event_status(event, arrived):
	status = event.get("status")
	if status not in ACTIVE:
		return status
	active = active_qty(event)
	if active <= 0:
		return RESOLVED_TO_STOCK
	if event.get("source_type") in IN_TRANSIT_SOURCES:
		return RECEIVED if flt(arrived) >= active else COMMITTED
	return RECEIVED


def is_live_unit(unit):
	return unit.get("status") != RETURNED and unit.get("destination") == ENCARGO_DESTINATION


def summarize(requested, events, units, invalid=0):
	"""All demand quantities from real data; repeated calls give the same result (Spec 020 §6, §10).

	invalid: covered units whose ERPNext reservation is gone or misplaced; still sourced, not covered.
	"""
	requested = flt(requested)
	arrived = {}
	posted = waiting = unlinked = 0
	for unit in units:
		if not is_live_unit(unit):
			continue
		if unit.get("supply_event"):
			arrived[unit["supply_event"]] = arrived.get(unit["supply_event"], 0) + 1
		else:
			unlinked += 1
		if unit.get("status") == POSTED:
			posted += 1
		else:
			waiting += 1
	sourced = unlinked
	stock = legacy = in_transit = exception = 0
	statuses = {}
	for event in events:
		got = arrived.get(event["name"], 0)
		statuses[event["name"]] = event_status(event, got)
		active = active_qty(event)
		sourced += active
		if event.get("source_type") == STOCK:
			stock += active
		elif event.get("source_type") == MIGRATION:
			legacy += active
		transit = in_transit_qty(event, got)
		in_transit += transit
		if event.get("barcode_exception_status") == PENDING_APPROVAL:
			exception += transit
	return frappe._dict(
		requested_qty=requested,
		sourced_qty=sourced,
		pending_supply_qty=max(requested - sourced, 0),
		received_qty=posted,
		waiting_qty=waiting,
		stock_qty=stock,
		legacy_qty=legacy,
		covered_qty=max(min(posted + stock + legacy, requested) - flt(invalid), 0),
		invalid_qty=flt(invalid),
		pending_receive_qty=in_transit,
		exception_qty=exception,
		event_status=statuses,
		event_received=arrived,
	)


def derived_purchase_status(current, events):
	"""purchase_status is only a compatibility mirror now (Spec 020 §12)."""
	if any(e.get("source_type") in PURCHASE_SOURCES and active_qty(e) > 0 for e in events):
		return "PURCHASED"
	return "PENDING" if current == "PURCHASED" else current


def derived_barcode_status(current, events):
	shopper = [e for e in events if e.get("source_type") in PURCHASE_SOURCES and e.get("barcode_exception_status")]
	if not shopper:
		return current
	if any(e.get("barcode_exception_status") == PENDING_APPROVAL and active_qty(e) > 0 for e in shopper):
		return PENDING_APPROVAL
	return sorted(shopper, key=lambda e: e.get("idx") or 0)[-1].get("barcode_exception_status")


def fifo_key(row):
	"""Demand FIFO is the Encargo creation, then name (Spec 020 §8)."""
	return (str(row.get("creation") or ""), row.get("name") or "")


def oldest_first(rows):
	return sorted(rows, key=fifo_key)


def _columns(fields):
	return ", ".join(f"`{field}`" for field in fields)


def locked_events(encargo):
	"""Locking read: sees events committed by another user after this transaction started."""
	return frappe.db.sql(
		f"select {_columns(EVENT_FIELDS)} from `tab{EVENT}` where parent=%s and parenttype='Encargo' "
		"order by idx asc for update",
		(encargo,),
		as_dict=True,
	)


def locked_units(encargo):
	return frappe.db.sql(
		f"select {_columns(UNIT_FIELDS)} from `tab{UNIT}` where encargo=%s for update",
		(encargo,),
		as_dict=True,
	)


def lock_encargo(encargo, fields=None):
	return frappe.db.get_value("Encargo", encargo, fields or ENCARGO_FIELDS, as_dict=True, for_update=True)


def add_event(encargo, source_type, status, qty, user, **values):
	"""Child row inserted directly: the Encargo document is never saved by these services."""
	name = frappe.generate_hash(length=10)
	idx = frappe.db.count(EVENT, {"parent": encargo, "parenttype": "Encargo"}) + 1
	frappe.get_doc(
		{
			"doctype": EVENT,
			"name": name,
			"parent": encargo,
			"parenttype": "Encargo",
			"parentfield": "supply_events",
			"idx": idx,
			"source_type": source_type,
			"status": status,
			"qty": flt(qty),
			"received_qty": 0,
			"released_qty": 0,
			"event_on": now_datetime(),
			"user": user,
			**values,
		}
	).db_insert()
	return name


def encargo_values(enc, events, totals):
	values = {
		"sourced_qty": totals.sourced_qty,
		"pending_supply_qty": totals.pending_supply_qty,
		"covered_qty": totals.covered_qty,
		"pending_receive_qty": totals.pending_receive_qty,
	}
	# Receptions marked before Spec 018 without units keep their stored figures.
	if not totals.legacy_qty and (
		totals.received_qty or totals.waiting_qty or enc.get("reception_status") in LIVE_RECEPTION
	):
		values["received_qty"] = totals.received_qty
		values["reception_status"] = RECEIVED if totals.received_qty >= totals.requested_qty else "PENDING"
	if events:
		values["purchase_status"] = derived_purchase_status(enc.get("purchase_status"), events)
		values["barcode_exception_status"] = derived_barcode_status(enc.get("barcode_exception_status"), events)
	return values


def reconcile_encargo_supply(encargo):
	"""Single routine run after every supply or coverage change (Spec 020 §10)."""
	enc = lock_encargo(encargo)
	if not enc:
		return None
	from erpn_custom.encargo import reservations

	events = locked_events(encargo)
	units = locked_units(encargo)
	totals = summarize(enc.requested_qty, events, units, reservations.encargo_invalid_qty(enc, events, units))
	for event in events:
		values = {}
		status = totals.event_status[event.name]
		received = totals.event_received.get(event.name, 0)
		if status != event.status:
			values["status"] = status
			event.status = status
		if flt(event.received_qty) != received:
			values["received_qty"] = received
		if values:
			frappe.db.set_value(EVENT, event.name, values, update_modified=False)
	values = encargo_values(enc, events, totals)
	changed = {k: v for k, v in values.items() if enc.get(k) != v}
	if changed:
		frappe.db.set_value("Encargo", encargo, changed, update_modified=True)
	return totals


def current_totals(doc):
	"""Non-locking figures for Encargo.validate (form saves and Spec 017 quantity adjustments)."""
	events = [row.as_dict() for row in doc.get("supply_events") or []]
	units = []
	if not doc.is_new():
		units = frappe.get_all(UNIT, filters={"encargo": doc.name}, fields=UNIT_FIELDS)
	return summarize(doc.requested_qty, events, units)
