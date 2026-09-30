from frappe.utils import add_days, nowdate

# Keep in sync with DEFAULT_DELIVERY_DAYS in public/js/sales_order.js.
DEFAULT_DELIVERY_DAYS = 7


def default_delivery_date(doc, method=None):
	"""Sales Order before_validate: an empty delivery date becomes order date + 7 days."""
	if getattr(doc, "doctype", None) != "Sales Order":
		return
	if doc.docstatus != 0 or doc.get("delivery_date"):
		return
	doc.delivery_date = add_days(doc.get("transaction_date") or nowdate(), DEFAULT_DELIVERY_DAYS)
