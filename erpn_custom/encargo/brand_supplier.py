import frappe
from frappe import _


def supplier_supplies_brand(supplier, brand):
	if not supplier or not brand:
		return False
	return bool(
		frappe.db.exists(
			"Supplier Brand",
			{"parent": supplier, "parenttype": "Supplier", "brand": brand},
		)
	)


def require_brand(brand):
	brand = (brand or "").strip()
	if not brand:
		frappe.throw(_("Brand is required"))
	if not frappe.db.exists("Brand", brand):
		frappe.throw(_("Brand {0} not found").format(brand))
	return brand


def optional_supplier_for_brand(brand, supplier):
	"""Brand firm; supplier suggested and must supply that brand when set."""
	brand = require_brand(brand)
	supplier = (supplier or "").strip() or None
	if not supplier:
		return brand, None
	if not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Supplier {0} not found").format(supplier))
	if frappe.db.get_value("Supplier", supplier, "disabled"):
		frappe.throw(_("Supplier {0} is disabled").format(supplier))
	if not supplier_supplies_brand(supplier, brand):
		frappe.throw(
			_("Supplier {0} does not supply Brand {1}. Add the brand on the Supplier.").format(
				supplier, brand
			)
		)
	return brand, supplier
