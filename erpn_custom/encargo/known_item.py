import frappe
from frappe import _

from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS

CLASSIFICATION_FIELDS = ("item_group", "custom_departamento", *ATTRIBUTE_FIELDS.values())
KNOWN_ITEM_FIELDS = ("brand", "size", "color", "description", "model", *CLASSIFICATION_FIELDS)


def known_item_values(item_code):
	"""Encargo fields fixed by the Item: same barcode means same brand, size and color."""
	item = frappe.db.get_value("Item", item_code, ["item_name", "brand", *CLASSIFICATION_FIELDS], as_dict=True)
	if not item:
		frappe.throw(_("Item {0} not found").format(item_code))
	values = {fieldname: item.get(fieldname) or None for fieldname in CLASSIFICATION_FIELDS}
	values.update(
		{
			"brand": item.get("brand"),
			"description": item.get("item_name") or item_code,
			"model": None,
		}
	)
	values.update(legacy_size_color(values))
	return values


def legacy_size_color(values):
	"""Text size/color read by shopper and reception, derived from the controlled lists."""
	return {
		"size": values.get("custom_talla") or values.get("custom_tamano") or None,
		"color": values.get("custom_color") or None,
	}
