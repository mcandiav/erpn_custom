import frappe

# Custom DocPerm rows inserted by SQL on 2026-09-20 for ComercialFRA. Once a doctype has any
# Custom DocPerm row Frappe ignores its standard DocPerm, so the standard roles lost access.
DOCTYPES = ("Shipment", "Courier Configuration", "Courier Provider")
SKIP_FIELDS = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"idx",
	"docstatus",
	"parent",
	"parenttype",
	"parentfield",
}


def execute():
	for doctype in DOCTYPES:
		if restore_standard_rows(doctype):
			frappe.clear_cache(doctype=doctype)


def restore_standard_rows(doctype):
	"""Copy missing standard rows into Custom DocPerm; existing custom rows stay untouched."""
	custom = frappe.get_all("Custom DocPerm", filters={"parent": doctype}, fields=["role", "permlevel", "if_owner"])
	if not custom:
		return 0
	present = {_key(row) for row in custom}
	columns = [
		df.fieldname for df in frappe.get_meta("Custom DocPerm").fields if df.fieldname not in SKIP_FIELDS
	]
	added = 0
	for row in frappe.get_all("DocPerm", filters={"parent": doctype}, fields=["*"]):
		if _key(row) in present:
			continue
		doc = {"doctype": "Custom DocPerm", "parent": doctype, "parenttype": "DocType", "parentfield": "permissions"}
		doc.update({field: row.get(field) for field in columns if field in row})
		frappe.get_doc(doc).insert(ignore_permissions=True)
		present.add(_key(row))
		added += 1
	return added


def _key(row):
	return (row.get("role"), int(row.get("permlevel") or 0), int(row.get("if_owner") or 0))
