"""Spec 020 §20: the single purchase stored on each Encargo becomes a supply event; idempotent."""

import frappe
from frappe.utils import flt

from erpn_custom.encargo import barcode_exception, demand

LEGACY_FIELDS = [
	"name",
	"owner",
	"modified",
	"requested_qty",
	"reception_status",
	"shopper_user",
	"purchased_on",
	"purchase_supplier",
	"proposed_supplier_name",
	"purchase_barcode",
	"purchase_price",
	"purchase_currency",
	"purchase_product_image",
	"purchase_label_image",
	"barcode_exception_status",
	"expected_barcode",
	"barcode_resolved_on",
	"barcode_resolved_by",
	"barcode_resolution_comment",
]
PRE_018_RECEIVED = ("RECEIVED", "RESOLVED_TO_ENC")
PRE_018_TO_STOCK = "RESOLVED_TO_STOCK"


def legacy_event(row, units):
	"""(source_type, status, released_qty) of the purchase stored on the Encargo."""
	qty = flt(row.get("requested_qty"))
	if row.get("barcode_exception_status") == "REJECTED":
		return demand.SHOPPER, demand.REJECTED, 0
	if not units and row.get("reception_status") in PRE_018_RECEIVED:
		return demand.MIGRATION, demand.RECEIVED, 0
	if not units and row.get("reception_status") == PRE_018_TO_STOCK:
		return demand.MIGRATION, demand.RESOLVED_TO_STOCK, 0
	# Returned units and pre-018 receptions resolved to stock no longer consume the demand.
	released = sum(1 for unit in units if not demand.is_live_unit(unit))
	return demand.SHOPPER, demand.COMMITTED, min(released, qty)


def execute():
	reopened = migrate_legacy_purchases()
	names = frappe.get_all("Encargo", pluck="name")
	for name in names:
		demand.reconcile_encargo_supply(name)
	print(f"Spec 020: {len(names)} Encargos reconciliados.")
	if reopened:
		print("Spec 020: demanda vuelve a la cola Shopper (compra rechazada o resuelta a stock): " + ", ".join(reopened))


def migrate_legacy_purchases():
	reopened = []
	rows = frappe.db.sql(
		f"""select {", ".join(f"e.`{f}`" for f in LEGACY_FIELDS)} from `tabEncargo` e
		where e.purchase_status='PURCHASED'
			and not exists (select 1 from `tab{demand.EVENT}` s where s.parent=e.name and s.parenttype='Encargo')""",
		as_dict=True,
	)
	for row in rows:
		units = frappe.get_all(demand.UNIT, filters={"encargo": row.name}, fields=demand.UNIT_FIELDS)
		source_type, status, released = legacy_event(row, units)
		event = demand.add_event(
			row.name,
			source_type,
			status,
			row.requested_qty,
			row.shopper_user or row.owner,
			released_qty=released,
			event_on=row.purchased_on or row.modified,
			migrated_from_legacy=1,
			shopper_user=row.shopper_user,
			purchased_on=row.purchased_on,
			supplier=row.purchase_supplier,
			proposed_supplier_name=row.proposed_supplier_name,
			purchase_barcode=row.purchase_barcode,
			purchase_price=row.purchase_price,
			purchase_currency=row.purchase_currency or "USD",
			purchase_product_image=row.purchase_product_image,
			purchase_label_image=row.purchase_label_image,
			barcode_exception_status=row.barcode_exception_status or None,
			expected_barcode=row.expected_barcode,
			barcode_resolved_on=row.barcode_resolved_on,
			barcode_resolved_by=row.barcode_resolved_by,
			barcode_resolution_comment=row.barcode_resolution_comment,
			notes="MIGRATED_FROM_LEGACY",
		)
		for unit in units:
			if not unit.supply_event:
				frappe.db.set_value(demand.UNIT, unit.name, "supply_event", event, update_modified=False)
		if status in demand.ACTIVE and row.barcode_exception_status == barcode_exception.PENDING_APPROVAL:
			# Fills the expected code if missing and keeps a single open ToDo per seller.
			barcode_exception.open_exception(row.name, event)
		if status in (demand.REJECTED, demand.RESOLVED_TO_STOCK):
			reopened.append(row.name)
	return reopened
