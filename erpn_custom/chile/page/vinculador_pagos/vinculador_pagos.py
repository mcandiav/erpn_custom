import frappe

from erpn_custom.chile.deposit_mapping import (
	assign_orphan_deposit,
	enqueue_deposit_mapping,
	get_pagos_clientes_data,
)

ALLOWED = ("System Manager", "Accounts Manager", "Accounts User")


@frappe.whitelist()
def enqueue_mapping():
	frappe.only_for(ALLOWED)
	return enqueue_deposit_mapping(source="Manual", requested_by=frappe.session.user)


@frappe.whitelist()
def dashboard(exception_start=0, exception_limit=50, orphan_start=0, orphan_limit=50):
	frappe.only_for(ALLOWED)
	return get_pagos_clientes_data(
		int(exception_start or 0),
		int(exception_limit or 50),
		int(orphan_start or 0),
		int(orphan_limit or 50),
	)


@frappe.whitelist()
def assign_orphan(bank_transaction, customer):
	frappe.only_for(ALLOWED)
	return assign_orphan_deposit(bank_transaction, customer)
