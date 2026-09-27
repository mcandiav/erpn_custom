import frappe
from frappe.utils import cint, flt

from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS, DEPARTMENTS
from erpn_custom.catalog.item import get_classification_options
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM

RESULT_LIMIT = 100
RESULT_FIELDS = ["name", "item_name", "brand", "item_group", "custom_departamento", *ATTRIBUTE_FIELDS.values()]


def departments_for(departamento):
	# Unisex products are offered to both women and men.
	if departamento in ("Mujer", "Hombre"):
		return [departamento, "Unisex"]
	return [departamento]


def build_filters(groups=None, brand=None, departamento=None, attributes=None):
	filters = {"disabled": 0, "has_variants": 0, "name": ["!=", ENCARGO_PENDIENTE_ITEM]}
	if groups is not None:
		filters["item_group"] = ["in", groups or [""]]
	if brand:
		filters["brand"] = brand
	if departamento:
		filters["custom_departamento"] = ["in", departments_for(departamento)]
	allowed = set(ATTRIBUTE_FIELDS.values())
	for fieldname, value in (attributes or {}).items():
		if value and fieldname in allowed:
			filters[fieldname] = value
	return filters


def available_qty(actual_qty, reserved_stock):
	return max(flt(actual_qty) - flt(reserved_stock), 0)


@frappe.whitelist()
def get_search_filters(item_group=None, departamento=None):
	"""Departments plus the attribute lists that apply to the chosen group."""
	data = get_classification_options(item_group, departamento)
	data["departamentos"] = list(DEPARTMENTS)
	return data


@frappe.whitelist()
def search_items(item_group=None, brand=None, departamento=None, text=None, warehouse=None, attributes=None):
	"""Items matching the facets, with stock in the order warehouse and in all warehouses."""
	frappe.has_permission("Item", "read", throw=True)
	groups = _descendant_groups(item_group) if item_group else None
	filters = build_filters(groups, brand, departamento, frappe.parse_json(attributes) if attributes else None)
	or_filters = None
	if text and text.strip():
		like = f"%{text.strip()}%"
		or_filters = [["name", "like", like], ["item_name", "like", like], ["custom_sku_proveedor", "like", like]]
	items = frappe.get_list(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=RESULT_FIELDS,
		order_by="brand asc, item_name asc",
		limit_page_length=RESULT_LIMIT + 1,
	)
	truncated = len(items) > RESULT_LIMIT
	items = items[:RESULT_LIMIT]
	_attach_stock(items, warehouse)
	return {"items": items, "truncated": cint(truncated), "limit": RESULT_LIMIT, "warehouse": warehouse}


def _descendant_groups(item_group):
	bounds = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
	if not bounds:
		return []
	return frappe.get_all(
		"Item Group", filters={"lft": [">=", bounds.lft], "rgt": ["<=", bounds.rgt]}, pluck="name"
	)


def _attach_stock(items, warehouse):
	codes = [item.name for item in items]
	bins = (
		frappe.get_all(
			"Bin",
			filters={"item_code": ["in", codes]},
			fields=["item_code", "warehouse", "actual_qty", "reserved_stock"],
		)
		if codes
		else []
	)
	total, in_warehouse = {}, {}
	for row in bins:
		total[row.item_code] = total.get(row.item_code, 0) + flt(row.actual_qty)
		if warehouse and row.warehouse == warehouse:
			in_warehouse[row.item_code] = available_qty(row.actual_qty, row.reserved_stock)
	for item in items:
		item["stock_total"] = total.get(item.name, 0)
		item["stock_bodega"] = in_warehouse.get(item.name, 0) if warehouse else None
