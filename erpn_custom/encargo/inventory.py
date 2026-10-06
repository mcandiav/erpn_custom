"""ERPNext inventory side of Recepción Chile (Spec 018): Item, Material Receipt, reservation and transfer."""

import re

import frappe
from frappe import _
from frappe.utils import flt, getdate, strip_html

from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS

SETTINGS = "Configuracion Recepcion FRA"
STOCK_WAREHOUSE = "Matriz - FRAG"
ENCARGO_WAREHOUSE_NAME = "Recepcion Encargos"
ENCARGO_WAREHOUSE = "Recepcion Encargos - FRAG"
ITEM_SERIES = "FRA-.#####"
STOCK_UOM = "Unidad"
ITEM_CODE_MAX = 40
CLEAN_ITEM_CODE = re.compile(r"^[A-Za-z0-9-]+$")
PURCHASE_CURRENCY = "USD"
FALLBACK_PAIR = ("USD", "CLP")


def pending_receive_qty(requested_qty, received_qty):
	return max(flt(requested_qty) - flt(received_qty), 0)


def usable_as_item_code(code):
	"""Letters, digits and hyphen up to 40 characters; URLs, QR payloads or spaces get an FRA- code."""
	code = code or ""
	return 0 < len(code) <= ITEM_CODE_MAX and bool(CLEAN_ITEM_CODE.match(code))


def choose_rate(erpnext_rate, fallback_rate, currency, company_currency):
	"""(rate, source) for converting the shopper price; (0, None) means pending valuation."""
	if currency == company_currency:
		return 1.0, "SAME_CURRENCY"
	if flt(erpnext_rate) > 0:
		return flt(erpnext_rate), "ERPNEXT"
	if (currency, company_currency) == FALLBACK_PAIR and flt(fallback_rate) > 0:
		return flt(fallback_rate), "FALLBACK"
	return 0.0, None


def choose_stock_rate(current_valuation, item_valuation, last_incoming):
	"""(rate, source) for a known Item without shopper price; never zero."""
	for rate, source in (
		(current_valuation, "VALUATION"),
		(item_valuation, "VALUATION"),
		(last_incoming, "LAST_INCOMING"),
	):
		if flt(rate) > 0:
			return flt(rate), source
	return 0.0, None


def known_item_decision(expected_item, barcode_item, expected_has_barcodes):
	"""Spec 018 §7: 'use' the expected Item, 'adopt' the code on it, or 'mismatch' (Spec 017)."""
	if barcode_item:
		return "use" if barcode_item == expected_item else "mismatch"
	return "mismatch" if expected_has_barcodes else "adopt"


def missing_classification(values, item_group_is_leaf):
	missing = []
	if not values.get("brand"):
		missing.append(_("marca"))
	if not values.get("item_group"):
		missing.append(_("grupo de producto"))
	elif not item_group_is_leaf:
		missing.append(_("grupo de producto de último nivel"))
	if not (values.get("description") or "").strip():
		missing.append(_("descripción"))
	return missing


def clearing_account_problem(account, company):
	if not account:
		return _("La cuenta transitoria no existe.")
	if account.get("is_group"):
		return _("La cuenta transitoria no puede ser una cuenta de grupo.")
	if account.get("account_type") == "Stock":
		return _("La cuenta transitoria no puede ser de tipo Stock.")
	if company and account.get("company") != company:
		return _("La cuenta transitoria debe pertenecer a la compañía {0}.").format(company)
	return None


def reception_company():
	return frappe.db.get_value("Warehouse", STOCK_WAREHOUSE, "company")


def clearing_account():
	return frappe.db.get_single_value(SETTINGS, "clearing_account")


def items_for_barcode(code):
	"""Items carrying exactly this code (the collation ignores case; short QR links do not)."""
	rows = frappe.get_all("Item Barcode", filters={"barcode": code, "parenttype": "Item"}, fields=["parent", "barcode"])
	return sorted({row.parent for row in rows if row.barcode == code})


def item_has_barcodes(item_code):
	return bool(frappe.db.exists("Item Barcode", {"parent": item_code, "parenttype": "Item"}))


def add_barcode(item_code, code):
	"""Attaches the scanned code; Item Barcode.barcode is unique, so a code never lands on two Items."""
	frappe.get_doc(
		{
			"doctype": "Item Barcode",
			"name": frappe.generate_hash(length=10),
			"parent": item_code,
			"parenttype": "Item",
			"parentfield": "barcodes",
			"idx": frappe.db.count("Item Barcode", {"parent": item_code, "parenttype": "Item"}) + 1,
			"barcode": code,
		}
	).db_insert()
	frappe.clear_document_cache("Item", item_code)


def new_item_code(code):
	from frappe.model.naming import make_autoname

	if usable_as_item_code(code) and not frappe.db.exists("Item", code):
		return code
	return make_autoname(ITEM_SERIES)


def create_item_from_encargo(encargo, code):
	"""(item_code, None) or (None, reason). The Item follows Spec 014: leaf group, brand, listed attributes."""
	is_leaf = bool(encargo.get("item_group")) and not frappe.db.get_value("Item Group", encargo.item_group, "is_group")
	missing = missing_classification(encargo, is_leaf)
	if missing:
		return None, _("Faltan datos para crear el Item: {0}.").format(", ".join(missing))
	description = encargo.description.strip()
	item = {
		"doctype": "Item",
		"item_code": new_item_code(code),
		"item_name": description[:140],
		"description": description,
		"item_group": encargo.item_group,
		"brand": encargo.brand,
		"stock_uom": STOCK_UOM,
		"is_stock_item": 1,
		"custom_departamento": encargo.get("custom_departamento") or None,
		"barcodes": [{"barcode": code}],
	}
	for fieldname in ATTRIBUTE_FIELDS.values():
		if encargo.get(fieldname):
			item[fieldname] = encargo.get(fieldname)
	frappe.db.savepoint("reception_item")
	try:
		doc = frappe.get_doc(item)
		doc.flags.ignore_permissions = True
		doc.insert()
	except Exception as e:
		frappe.db.rollback(save_point="reception_item")
		frappe.clear_messages()
		return None, _("No se pudo crear el Item: {0}").format(strip_html(str(e)))[:500]
	return doc.name, None


def exchange_rate(currency, company_currency, on_date):
	erpnext_rate = 0
	if currency != company_currency:
		try:
			from erpnext.setup.utils import get_exchange_rate

			erpnext_rate = get_exchange_rate(currency, company_currency, str(getdate(on_date)), "for_buying")
		except Exception:
			erpnext_rate = 0
		frappe.clear_messages()
	fallback = frappe.db.get_single_value(SETTINGS, "fallback_usd_clp_rate")
	return choose_rate(erpnext_rate, fallback, currency, company_currency)


def stock_rate(item_code, warehouse):
	current = frappe.db.get_value(
		"Stock Ledger Entry",
		{"item_code": item_code, "warehouse": warehouse, "is_cancelled": 0},
		"valuation_rate",
		order_by="posting_date desc, posting_time desc, creation desc",
	)
	item_valuation = frappe.db.get_value("Item", item_code, "valuation_rate")
	last_incoming = frappe.db.get_value(
		"Stock Ledger Entry",
		{"item_code": item_code, "is_cancelled": 0, "actual_qty": (">", 0), "incoming_rate": (">", 0)},
		"incoming_rate",
		order_by="posting_date desc, posting_time desc, creation desc",
	)
	return choose_stock_rate(current, item_valuation, last_incoming)


def make_receipt(company, item_code, warehouse, rate, account, remarks):
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Receipt"
	se.purpose = "Material Receipt"
	se.company = company
	se.remarks = remarks
	se.append(
		"items",
		{
			"item_code": item_code,
			"qty": 1,
			"t_warehouse": warehouse,
			"basic_rate": flt(rate),
			# A manual rate skips the server-side amount; without it the entry totals read 0.
			"basic_amount": flt(rate),
			"set_basic_rate_manually": 1,
			"expense_account": account,
		},
	)
	se.flags.ignore_permissions = True
	se.insert()
	se.submit()
	return se.name


def make_transfer(company, item_code, source, target, remarks):
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.purpose = "Material Transfer"
	se.company = company
	se.remarks = remarks
	se.append("items", {"item_code": item_code, "qty": 1, "s_warehouse": source, "t_warehouse": target})
	se.flags.ignore_permissions = True
	se.insert()
	se.submit()
	return se.name


def reserve_unit(sales_order, sales_order_item, item_code, warehouse):
	"""(Stock Reservation Entry, None) or (None, reason). One entry per unit so a return cancels exactly it."""
	if not frappe.db.get_single_value("Stock Settings", "enable_stock_reservation"):
		return None, _("La reserva de stock está deshabilitada en Stock Settings.")
	from erpnext.selling.doctype.sales_order.sales_order import get_unreserved_qty
	from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
		get_available_qty_to_reserve,
		get_sre_reserved_qty_details_for_voucher,
	)

	so_item = frappe.db.get_value(
		"Sales Order Item",
		sales_order_item,
		["name", "parent", "item_code", "stock_qty", "delivered_qty", "conversion_factor", "stock_uom", "docstatus"],
		as_dict=True,
	)
	if not so_item or so_item.parent != sales_order or so_item.docstatus != 1:
		return None, _("La línea de la Orden de Venta no está validada.")
	if so_item.item_code != item_code:
		return None, _("La línea de la Orden de Venta tiene otro Item ({0}).").format(so_item.item_code)
	if get_unreserved_qty(so_item, get_sre_reserved_qty_details_for_voucher("Sales Order", sales_order)) < 1:
		return None, _("La línea de la Orden de Venta ya está reservada completa.")
	available = flt(get_available_qty_to_reserve(item_code, warehouse))
	if available < 1:
		return None, _("No hay stock disponible para reservar en {0}.").format(warehouse)
	company, project = frappe.db.get_value("Sales Order", sales_order, ["company", "project"])
	has_serial_no, has_batch_no = frappe.get_cached_value("Item", item_code, ["has_serial_no", "has_batch_no"])
	frappe.db.savepoint("reception_reservation")
	try:
		sre = frappe.new_doc("Stock Reservation Entry")
		sre.item_code = item_code
		sre.warehouse = warehouse
		sre.has_serial_no = has_serial_no
		sre.has_batch_no = has_batch_no
		sre.voucher_type = "Sales Order"
		sre.voucher_no = sales_order
		sre.voucher_detail_no = sales_order_item
		sre.available_qty = available
		sre.voucher_qty = so_item.stock_qty
		sre.reserved_qty = 1
		sre.company = company
		sre.stock_uom = so_item.stock_uom
		sre.project = project
		sre.flags.ignore_permissions = True
		sre.insert()
		sre.submit()
		frappe.db.set_value("Sales Order Item", sales_order_item, "reserve_stock", 1, update_modified=False)
	except Exception as e:
		frappe.db.rollback(save_point="reception_reservation")
		frappe.clear_messages()
		return None, _("Reserva no aplicada: {0}").format(strip_html(str(e)))[:500]
	return sre.name, None


def cancel_reservation(name):
	if not name or frappe.db.get_value("Stock Reservation Entry", name, "docstatus") != 1:
		return
	sre = frappe.get_doc("Stock Reservation Entry", name)
	sre.flags.ignore_permissions = True
	sre.cancel()
