import frappe
from frappe import _

from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM

SUMMARY_FIELDS = (
	("brand", "Marca"),
	("item_group", "Grupo"),
	("custom_departamento", "Departamento"),
	*((fieldname, attribute) for attribute, fieldname in ATTRIBUTE_FIELDS.items()),
	("model", "Modelo"),
)
LINE_FIELDS = ("description", "reference_image", *(fieldname for fieldname, _label in SUMMARY_FIELDS))


def line_description(encargo):
	"""Description of the Sales Order line: what the seller wrote plus the chosen characteristics."""
	parts = [f"{_(label)}: {encargo.get(fieldname)}" for fieldname, label in SUMMARY_FIELDS if encargo.get(fieldname)]
	text = (encargo.get("description") or "").strip()
	return f"{text} — {' | '.join(parts)}" if parts else text


def line_values(encargo):
	return {"description": line_description(encargo), "image": encargo.get("reference_image") or None}


def sync_sales_order_line(encargo):
	"""Copy the Encargo characteristics to its ENCARGO-PENDIENTE line while the order is a Draft."""
	if encargo.get("source_type") != "UNKNOWN_ITEM" or not encargo.get("sales_order_item"):
		return
	if frappe.db.get_value("Sales Order", encargo.get("sales_order"), "docstatus") != 0:
		return
	frappe.db.set_value("Sales Order Item", encargo.get("sales_order_item"), line_values(encargo), update_modified=False)


def refresh_encargo_lines(doc, method=None):
	"""Sales Order validate: the lines always show the current Encargo, even if the form was stale."""
	for item in doc.items:
		if item.item_code != ENCARGO_PENDIENTE_ITEM or not item.get("custom_encargo"):
			continue
		encargo = frappe.db.get_value("Encargo", item.custom_encargo, LINE_FIELDS, as_dict=True)
		if encargo:
			item.update(line_values(encargo))
