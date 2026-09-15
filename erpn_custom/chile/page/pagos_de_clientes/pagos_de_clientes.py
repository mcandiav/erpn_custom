import frappe

from erpn_custom.chile.deposit_mapping import enqueue_deposit_mapping, get_pagos_clientes_data

ALLOWED = ("System Manager", "Accounts Manager", "Accounts User")


@frappe.whitelist()
def enqueue_mapping():
    frappe.only_for(ALLOWED)
    return enqueue_deposit_mapping(source="Manual", requested_by=frappe.session.user)


@frappe.whitelist()
def dashboard(exception_start=0, exception_limit=50):
    frappe.only_for(ALLOWED)
    return get_pagos_clientes_data(int(exception_start or 0), int(exception_limit or 50))
