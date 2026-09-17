import frappe

from erpn_custom.chile.courier_credentials import (
	STANDARD_COURIER_CREDENTIAL_KEYS,
	default_credential_rows,
)


def execute():
	"""Ensure each Courier Configuration has the 3 standard rows (keep secrets/URLs)."""
	for name in frappe.get_all("Courier Configuration", pluck="name"):
		doc = frappe.get_doc("Courier Configuration", name)
		by_key = {
			(row.credential_key or "").strip(): row for row in (doc.credentials or [])
		}
		changed = False
		for key in STANDARD_COURIER_CREDENTIAL_KEYS:
			if key not in by_key:
				doc.append("credentials", {"credential_key": key})
				changed = True
		if changed or not doc.credentials:
			if not doc.credentials:
				doc.set("credentials", default_credential_rows())
			doc.save(ignore_permissions=True)
