import frappe
from frappe import _
from frappe.utils import cint, flt

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM
from erpn_custom.encargo.stock_split import allocate_available_across_rows, available_to_sell


def before_submit(doc, method=None):
	if getattr(doc, "doctype", None) != "Sales Order":
		return
	apply_stock_encargo_split(doc)
	validate_unknown_item_rows(doc)
	ensure_encargos_for_known_shortfalls(doc)
	# Drive SRE from our hook; avoid native full-line auto-reserve.
	doc.reserve_stock = 0
	for item in doc.items:
		if flt(item.get("custom_stock_committed_qty")) > 0:
			item.reserve_stock = 1
		else:
			item.reserve_stock = 0


def on_submit(doc, method=None):
	if getattr(doc, "doctype", None) != "Sales Order":
		return
	activate_draft_encargos(doc)
	reserve_committed_stock(doc)


def on_cancel(doc, method=None):
	if getattr(doc, "doctype", None) != "Sales Order":
		return
	cancel_or_block_encargos(doc)


def apply_stock_encargo_split(doc):
	"""Write custom_stock_committed_qty / custom_encargo_qty on each row."""
	groups = {}
	for item in doc.items:
		if item.item_code == ENCARGO_PENDIENTE_ITEM:
			item.custom_stock_committed_qty = 0
			item.custom_encargo_qty = flt(item.qty)
			continue
		if not cint(item.get("is_stock_item") if item.get("is_stock_item") is not None else _is_stock_item(item.item_code)):
			item.custom_stock_committed_qty = 0
			item.custom_encargo_qty = 0
			continue
		key = (item.item_code, item.warehouse or doc.set_warehouse)
		groups.setdefault(key, []).append(item)

	for (item_code, warehouse), rows in groups.items():
		avail = _bin_available(item_code, warehouse)
		allocations = allocate_available_across_rows(
			[{"qty": row.qty} for row in rows],
			avail,
		)
		for row, (stock_committed, encargo_qty) in zip(rows, allocations):
			row.custom_stock_committed_qty = stock_committed
			row.custom_encargo_qty = encargo_qty


def validate_unknown_item_rows(doc):
	for item in doc.items:
		if item.item_code != ENCARGO_PENDIENTE_ITEM:
			continue
		if not item.get("custom_encargo"):
			frappe.throw(
				_("Row #{0}: ENCARGO-PENDIENTE requires a linked Encargo. Use Agregar Encargo.").format(
					item.idx
				)
			)


def ensure_encargos_for_known_shortfalls(doc):
	sales_person = _first_sales_person(doc)
	for item in doc.items:
		if item.item_code == ENCARGO_PENDIENTE_ITEM:
			continue
		encargo_qty = flt(item.get("custom_encargo_qty"))
		if encargo_qty <= 0:
			continue
		pair = _item_brand_store_pair(item.item_code)
		if not pair:
			frappe.throw(
				_(
					"Row #{0}: Item {1} requires Marca / Tienda (par Encargo) before creating Encargo. Set it on the Item."
				).format(item.idx, item.item_code)
			)
		existing = item.get("custom_encargo")
		if existing and frappe.db.exists("Encargo", existing):
			_sync_known_encargo(existing, doc, item, encargo_qty, sales_person, pair)
			continue
		by_row = frappe.db.get_value("Encargo", {"sales_order_item": item.name}, "name")
		if by_row:
			item.custom_encargo = by_row
			_sync_known_encargo(by_row, doc, item, encargo_qty, sales_person, pair)
			continue
		enc = frappe.get_doc(
			{
				"doctype": "Encargo",
				"naming_series": "ENC-.YYYY.-.#####",
				"status": "Draft",
				"source_type": "KNOWN_ITEM",
				"sales_order": doc.name,
				"sales_order_item": item.name,
				"customer": doc.customer,
				"sales_person": sales_person,
				"description": item.description or item.item_name or item.item_code,
				"expected_item": item.item_code,
				"encargo_brand_store": pair["name"],
				"brand": pair["brand"],
				"suggested_store": pair["store"],
				"requested_qty": encargo_qty,
				"sale_rate": item.rate,
				"purchase_status": "PENDING",
				"reception_status": "PENDING",
			}
		)
		enc.insert(ignore_permissions=True)
		item.custom_encargo = enc.name


def _item_brand_store_pair(item_code):
	pair_name = frappe.db.get_value("Item", item_code, "custom_encargo_brand_store")
	if not pair_name:
		return None
	pair = frappe.db.get_value(
		"Encargo Brand Store",
		pair_name,
		["name", "brand", "store", "enabled"],
		as_dict=True,
	)
	if not pair or not pair.get("enabled"):
		return None
	if frappe.db.get_value("Encargo Store", pair.get("store"), "enabled") == 0:
		return None
	return pair


def _sync_known_encargo(name, doc, item, encargo_qty, sales_person, pair=None):
	values = {
		"sales_order": doc.name,
		"customer": doc.customer,
		"sales_person": sales_person,
		"expected_item": item.item_code,
		"requested_qty": encargo_qty,
		"sale_rate": item.rate,
		"description": item.description or item.item_name or item.item_code,
		"source_type": "KNOWN_ITEM",
	}
	if pair:
		values["encargo_brand_store"] = pair["name"]
		values["brand"] = pair["brand"]
		values["suggested_store"] = pair["store"]
	frappe.db.set_value("Encargo", name, values, update_modified=False)


def activate_draft_encargos(doc):
	names = frappe.get_all(
		"Encargo",
		filters={"sales_order": doc.name, "status": "Draft"},
		pluck="name",
	)
	for name in names:
		frappe.db.set_value(
			"Encargo",
			name,
			{"status": "Open", "purchase_status": "PENDING"},
			update_modified=True,
		)


def reserve_committed_stock(doc):
	if not frappe.get_single_value("Stock Settings", "enable_stock_reservation"):
		return
	details = []
	for item in doc.items:
		qty = flt(item.get("custom_stock_committed_qty"))
		if qty <= 0:
			continue
		frappe.db.set_value(
			"Sales Order Item",
			item.name,
			"reserve_stock",
			1,
			update_modified=False,
		)
		details.append(
			{
				"sales_order_item": item.name,
				"warehouse": item.warehouse,
				"qty_to_reserve": qty,
				"conversion_factor": item.conversion_factor or 1,
			}
		)
	if not details:
		return
	doc.reload()
	doc.create_stock_reservation_entries(items_details=details, notify=False)


def cancel_or_block_encargos(doc):
	rows = frappe.get_all(
		"Encargo",
		filters={"sales_order": doc.name, "status": ["!=", "Cancelled"]},
		fields=["name", "purchase_status", "status"],
	)
	purchased = [r for r in rows if r.purchase_status == "PURCHASED"]
	if purchased:
		frappe.throw(
			_(
				"Cannot cancel Sales Order {0}: Encargo {1} already marked PURCHASED. Resolve explicitly before cancel."
			).format(doc.name, purchased[0].name)
		)
	for row in rows:
		frappe.db.set_value("Encargo", row.name, "status", "Cancelled", update_modified=True)


def _bin_available(item_code, warehouse):
	if not item_code or not warehouse:
		return 0.0
	try:
		from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
			get_available_qty_to_reserve,
		)

		return flt(get_available_qty_to_reserve(item_code, warehouse))
	except Exception:
		row = frappe.db.get_value(
			"Bin",
			{"item_code": item_code, "warehouse": warehouse},
			["actual_qty", "reserved_qty"],
			as_dict=True,
		)
		if not row:
			return 0.0
		return available_to_sell(row.actual_qty, row.reserved_qty)


def _is_stock_item(item_code):
	return cint(frappe.get_cached_value("Item", item_code, "is_stock_item"))


def _first_sales_person(doc):
	for row in doc.get("sales_team") or []:
		if row.sales_person:
			return row.sales_person
	return None
