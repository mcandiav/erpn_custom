import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.chile.realize_rules import allocation_plan, proposed_apply_amount, remaining_order_amount

ALLOWED = (
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"Sales Manager",
	"Sales User",
	"ComercialFRA",
)


@frappe.whitelist()
def credit_summary(sales_order=None, customer=None):
	frappe.only_for(ALLOWED)
	so = None
	if sales_order and frappe.db.exists("Sales Order", sales_order):
		so = _load_sales_order(sales_order)
	customer = (so.customer if so else None) or customer
	if not customer:
		frappe.throw(_("Seleccione un cliente"))
	available, payments = _available_credit(customer)
	grand_total = flt(so.rounded_total or so.grand_total) if so else 0
	advance_paid = _applied_to_order(so.name) if so else 0
	pending = remaining_order_amount(grand_total, advance_paid)
	return {
		"customer": customer,
		"sales_order": so.name if so else None,
		"available": available,
		"grand_total": grand_total,
		"advance_paid": advance_paid,
		"pending": pending,
		"proposed": proposed_apply_amount(available, pending),
		"payments": payments,
	}


@frappe.whitelist()
def apply_credit(sales_order, amount):
	frappe.only_for(ALLOWED)
	so = _load_sales_order(sales_order)
	if int(so.docstatus or 0) == 2:
		frappe.throw(_("No se puede aplicar saldo a una Orden de Venta cancelada"))
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("El monto aplicado debe ser mayor que cero"))
	summary = credit_summary(sales_order=so.name)
	if amount > flt(summary["available"]):
		frappe.throw(_("No se puede aplicar mas que el saldo a favor disponible"))
	if amount > flt(summary["pending"]):
		frappe.throw(_("No se puede aplicar mas que el saldo pendiente de esta Nota de Venta"))

	payments = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": so.customer,
			"unallocated_amount": [">", 0],
		},
		fields=["name", "unallocated_amount", "paid_from", "posting_date", "company"],
		order_by="posting_date asc, creation asc, name asc",
	)
	plan, leftover = allocation_plan(payments, amount)
	if leftover > 0.0001 or not plan:
		frappe.throw(_("No hay Payment Entry nativo suficiente para cubrir el monto"))

	from erpnext.accounts.utils import reconcile_against_document

	outstanding = flt(summary["pending"])
	grand_total = flt(summary["grand_total"])
	applied = []
	for item in plan:
		pe = frappe.get_doc("Payment Entry", item["name"])
		reconcile_against_document(
			[
				frappe._dict(
					{
						"voucher_type": "Payment Entry",
						"voucher_no": pe.name,
						"voucher_detail_no": None,
						"against_voucher_type": "Sales Order",
						"against_voucher": so.name,
						"account": pe.paid_from,
						"exchange_rate": pe.source_exchange_rate or 1,
						"party_type": "Customer",
						"party": so.customer,
						"is_advance": "Yes",
						"dr_or_cr": "credit_in_account_currency",
						"unreconciled_amount": flt(pe.unallocated_amount),
						"unadjusted_amount": flt(pe.unallocated_amount),
						"allocated_amount": flt(item["amount"]),
						"difference_amount": 0,
						"grand_total": grand_total,
						"outstanding_amount": outstanding,
					}
				)
			]
		)
		outstanding = flt(outstanding - item["amount"])
		applied.append({"payment_entry": pe.name, "amount": item["amount"]})

	advance_paid = _sync_advance_paid(so)
	frappe.db.commit()
	so.reload()
	return {
		"ok": True,
		"applied": applied,
		"advance_paid": advance_paid,
		"available": _available_credit(so.customer)[0],
		"pending": remaining_order_amount(so.rounded_total or so.grand_total, advance_paid),
	}


@frappe.whitelist()
def release_credit(sales_order, payment_entry=None):
	frappe.only_for(ALLOWED)
	so = _load_sales_order(sales_order)
	filters = {
		"parenttype": "Payment Entry",
		"reference_doctype": "Sales Order",
		"reference_name": so.name,
		"docstatus": 1,
	}
	if payment_entry:
		filters["parent"] = payment_entry
	rows = frappe.get_all(
		"Payment Entry Reference",
		filters=filters,
		fields=["parent", "allocated_amount"],
	)
	if not rows:
		frappe.throw(_("No hay saldo aplicado para revertir en esta Orden de Venta"))

	from erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment import (
		create_unreconcile_doc_for_selection,
	)

	import json

	company = so.company
	payload = []
	for row in rows:
		payload.append(
			{
				"company": company,
				"voucher_type": "Payment Entry",
				"voucher_no": row.parent,
				"against_voucher_type": "Sales Order",
				"against_voucher_no": so.name,
			}
		)
	create_unreconcile_doc_for_selection(json.dumps(payload))
	advance_paid = _sync_advance_paid(so)
	frappe.db.commit()
	so.reload()
	return {
		"ok": True,
		"advance_paid": advance_paid,
		"available": _available_credit(so.customer)[0],
	}


@frappe.whitelist()
def restore_unapplied_credit(sales_order):
	frappe.only_for(ALLOWED)
	so = _load_sales_order(sales_order)
	restored = _unlink_order_from_payment_entries(so.name)
	advance_paid = _sync_advance_paid(so)
	frappe.db.commit()
	return {
		"ok": True,
		"restored": restored,
		"advance_paid": advance_paid,
		"available": _available_credit(so.customer)[0],
	}


def _load_sales_order(name):
	if not name:
		frappe.throw(_("Falta la Orden de Venta"))
	return frappe.get_doc("Sales Order", name)


def _applied_to_order(sales_order):
	rows = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": "Sales Order",
			"reference_name": sales_order,
			"docstatus": 1,
		},
		fields=["allocated_amount"],
	)
	return flt(sum(flt(row.allocated_amount) for row in rows))


def _sync_advance_paid(so):
	allocated = _applied_to_order(so.name)
	so.db_set("advance_paid", allocated, update_modified=True)
	return allocated


def _unlink_order_from_payment_entries(sales_order):
	rows = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": "Sales Order",
			"reference_name": sales_order,
			"docstatus": 1,
		},
		fields=["parent", "allocated_amount"],
	)
	restored = []
	seen = []
	for row in rows:
		if row.parent in seen:
			continue
		seen.append(row.parent)
		pe = frappe.get_doc("Payment Entry", row.parent)
		pe.flags.ignore_validate_update_after_submit = True
		pe.flags.ignore_reposting_on_reconciliation = True
		removed = 0
		for reference in list(pe.get("references") or []):
			if reference.reference_doctype == "Sales Order" and reference.reference_name == sales_order:
				removed = flt(removed + (reference.allocated_amount or 0))
				pe.remove(reference)
		if not removed:
			continue
		pe.setup_party_account_field()
		pe.set_missing_values()
		pe.set_amounts()
		pe.save(ignore_permissions=True)
		restored.append({"payment_entry": pe.name, "amount": removed})
	return restored


def _available_credit(customer):
	payments = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": customer,
			"unallocated_amount": [">", 0],
		},
		fields=["name", "unallocated_amount", "posting_date"],
		order_by="posting_date asc, creation asc, name asc",
	)
	total = sum(flt(row.unallocated_amount) for row in payments)
	return flt(total), payments
