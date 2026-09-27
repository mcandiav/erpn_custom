import frappe
from frappe import _

KNOWN_ITEM_FIELDS = ("brand", "size", "color", "description", "model")


def known_item_values(item_code):
	"""Encargo fields fixed by the Item: same barcode means same brand, size and color."""
	item = frappe.db.get_value(
		"Item",
		item_code,
		["item_name", "brand", "custom_color", "custom_talla", "custom_tamano"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("Item {0} not found").format(item_code))
	return {
		"brand": item.get("brand"),
		"size": item.get("custom_talla") or item.get("custom_tamano") or None,
		"color": item.get("custom_color") or None,
		"description": item.get("item_name") or item_code,
		"model": None,
	}
