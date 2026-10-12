import frappe

from erpn_custom.patches.v0_0_45_restore_standard_perms import restore_standard_rows


def execute():
	# Delivery Note was left with only the ComercialFRA Custom DocPerm row, hiding it from its standard roles.
	if restore_standard_rows("Delivery Note"):
		frappe.clear_cache(doctype="Delivery Note")
