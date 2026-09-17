import frappe

from erpn_custom.chile.courier_credentials import default_credential_rows


def execute():
	"""Reset credential rows to the 3 standard services (overwrite secrets)."""
	for name in frappe.get_all("Courier Configuration", pluck="name"):
		doc = frappe.get_doc("Courier Configuration", name)
		doc.set("credentials", default_credential_rows())
		doc.save(ignore_permissions=True)
