from contextlib import contextmanager

import frappe

from erpn_custom.chile.payment_roles import needs_accounting_elevation


@contextmanager
def accounting_context():
	"""ERPNext's update_bank_transaction / create_payment_entry_bts check permissions as the
	session user; operational roles run them as Administrator without gaining DocType rights.
	Callers must have validated PAYMENT_OPERATION_ROLES first."""
	if not needs_accounting_elevation(frappe.get_roles()):
		yield
		return
	user = frappe.session.user
	sid = frappe.session.sid
	data = frappe.session.data
	form_dict = frappe.local.form_dict
	frappe.set_user("Administrator")
	try:
		yield
	finally:
		frappe.set_user(user)
		frappe.session.sid = sid
		frappe.session.data = data
		frappe.local.form_dict = form_dict
