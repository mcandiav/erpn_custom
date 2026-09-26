# doctype -> (default series, return series or None). Counters restart every year.
DOCUMENT_SERIES = {
	"Quotation": ("COT-.YYYY.-", None),
	"Sales Order": ("OV-.YYYY.-", None),
	"Delivery Note": ("NE-.YYYY.-", "NE-DEV-.YYYY.-"),
	"Sales Invoice": ("FAC-.YYYY.-", "NC-.YYYY.-"),
	"Payment Entry": ("PAG-.YYYY.-", None),
	"Journal Entry": ("AST-.YYYY.-", None),
	"Bank Transaction": ("MB-.YYYY.-", None),
	"Material Request": ("SM-.YYYY.-", None),
	"Request for Quotation": ("SC-.YYYY.-", None),
	"Supplier Quotation": ("CP-.YYYY.-", None),
	"Purchase Order": ("OC-.YYYY.-", None),
	"Purchase Receipt": ("REC-.YYYY.-", "REC-DEV-.YYYY.-"),
	"Purchase Invoice": ("FC-.YYYY.-", "NCC-.YYYY.-"),
	"Stock Entry": ("MOV-.YYYY.-", None),
	"Stock Reconciliation": ("AJU-.YYYY.-", None),
	"Pick List": ("PICK-.YYYY.-", None),
	"Lead": ("PROS-.YYYY.-", None),
	"Opportunity": ("OPO-.YYYY.-", None),
}


def series_options(doctype):
	default, return_series = DOCUMENT_SERIES[doctype]
	return [default, return_series] if return_series else [default]


def apply_document_series():
	import frappe
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for doctype, (default, _return_series) in DOCUMENT_SERIES.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.get_meta(doctype).get_field("naming_series"):
			continue
		options = "\n".join(series_options(doctype))
		make_property_setter(doctype, "naming_series", "options", options, "Text", validate_fields_for_doctype=False)
		make_property_setter(doctype, "naming_series", "default", default, "Text", validate_fields_for_doctype=False)
		frappe.clear_cache(doctype=doctype)


def set_return_series(doc, method=None):
	entry = DOCUMENT_SERIES.get(doc.doctype)
	if not entry or not entry[1] or not doc.get("is_return"):
		return
	if doc.get("naming_series") in (None, "", entry[0]):
		doc.naming_series = entry[1]
