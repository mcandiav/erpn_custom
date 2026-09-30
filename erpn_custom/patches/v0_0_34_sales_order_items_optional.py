import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	# Draft Sales Order may be saved empty; before_submit requires at least one line.
	make_property_setter("Sales Order", "items", "reqd", "0", "Check", validate_fields_for_doctype=False)
	frappe.clear_cache(doctype="Sales Order")
