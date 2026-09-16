import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.chile.realize_rules import allocation_plan, proposed_apply_amount

ALLOWED = (
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"Sales Manager",
	"Sales User",
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
	advance_paid = flt(so.advance_paid) if so else 0
	pending = flt(grand_total - advance_paid)
	if pending < 0:
		pending = 0
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

	so.reload()
	frappe.db.commit()
	return {
		"ok": True,
		"applied": applied,
		"advance_paid": flt(so.advance_paid),
		"available": _available_credit(so.customer)[0],
		"pending": flt((so.rounded_total or so.grand_total) - so.advance_paid),
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
	so.reload()
	frappe.db.commit()
	return {
		"ok": True,
		"advance_paid": flt(so.advance_paid),
		"available": _available_credit(so.customer)[0],
	}


def _load_sales_order(name):
	if not name:
		frappe.throw(_("Falta la Orden de Venta"))
	return frappe.get_doc("Sales Order", name)


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
