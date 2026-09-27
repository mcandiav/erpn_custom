import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from erpn_custom.catalog.attributes import (
	ATTRIBUTE_FIELDS,
	DEPARTMENTS,
	FAMILY_ATTRIBUTES,
	SEED_VALUES,
	make_abbr,
	seed_rows,
)
from erpn_custom.catalog.tree import iter_nodes

SELLER_ROLE = "ComercialFRA"
ADMIN_ROLE = "System Manager"
ADMIN_PTYPES = ("read", "select", "write", "create", "delete", "report", "export")


def apply_product_classification():
	apply_tree()
	apply_attribute_value_fields()
	apply_attributes()
	apply_item_fields()
	apply_permissions()
	frappe.clear_cache()


def apply_tree():
	"""Create or re-parent the tree. Existing groups with the same name are reused."""
	for name, parent, is_group in iter_nodes():
		existing = frappe.db.get_value("Item Group", name, "name")
		if existing:
			doc = frappe.get_doc("Item Group", existing)
			if doc.parent_item_group == parent and (doc.is_group or not is_group):
				continue
			doc.parent_item_group = parent
			doc.is_group = doc.is_group or is_group
			doc.save(ignore_permissions=True)
			continue
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": name,
				"parent_item_group": parent,
				"is_group": is_group,
			}
		).insert(ignore_permissions=True)


def apply_attribute_value_fields():
	create_custom_fields(
		{
			"Item Attribute Value": [
				{
					"fieldname": "custom_departamento",
					"label": "Departamento",
					"fieldtype": "Select",
					"options": "\n" + "\n".join(DEPARTMENTS),
					"insert_after": "abbr",
					"in_list_view": 1,
					"description": "Solo tallas: departamento al que pertenece la medida. Vacío = aplica a todos.",
				},
				{
					"fieldname": "custom_familia",
					"label": "Familia",
					"fieldtype": "Select",
					"options": "\nCalzado\nRopa",
					"insert_after": "custom_departamento",
					"in_list_view": 1,
					"description": "Solo tallas: familia a la que pertenece la medida. Vacío = aplica a todas.",
				},
			]
		},
		ignore_validate=True,
		update=True,
	)


def apply_attributes():
	"""Create the attribute lists and add missing seed values; never removes values."""
	for attribute in SEED_VALUES:
		exists = frappe.db.exists("Item Attribute", attribute)
		if exists:
			doc = frappe.get_doc("Item Attribute", attribute)
		else:
			doc = frappe.new_doc("Item Attribute")
			doc.attribute_name = attribute
		present = {row.attribute_value.lower(): row for row in doc.item_attribute_values}
		taken = [row.abbr for row in doc.item_attribute_values]
		changed = not exists
		for value, dept, family in seed_rows(attribute):
			row = present.get(value.lower())
			if row:
				# Fill scope only where the Administrator left it empty.
				for fieldname, seed in (("custom_departamento", dept), ("custom_familia", family)):
					if seed and not row.get(fieldname):
						row.set(fieldname, seed)
						changed = True
				continue
			abbr = make_abbr(value, taken)
			taken.append(abbr)
			doc.append(
				"item_attribute_values",
				{
					"attribute_value": value,
					"abbr": abbr,
					"custom_departamento": dept or None,
					"custom_familia": family or None,
				},
			)
			changed = True
		if changed:
			doc.save(ignore_permissions=True)


def apply_item_fields():
	def shown_for(attribute):
		families = [family for family, attrs in FAMILY_ATTRIBUTES.items() if attribute in attrs]
		if not families:
			return None
		return "eval:" + " || ".join(f"doc.custom_familia=='{family}'" for family in families)

	fields = [
		{
			# Frappe places a custom Section Break before the next section of its anchor:
			# after stock_uom it lands right below the Details header block.
			"fieldname": "custom_clasificacion_section",
			"label": "Clasificación",
			"fieldtype": "Section Break",
			"insert_after": "stock_uom",
		},
		{
			"fieldname": "custom_familia",
			"label": "Familia",
			"fieldtype": "Link",
			"options": "Item Group",
			"read_only": 1,
			"in_standard_filter": 1,
			"search_index": 1,
			"insert_after": "custom_clasificacion_section",
			"description": "Se calcula desde el Grupo de producto.",
		},
		{
			"fieldname": "custom_departamento",
			"label": "Departamento",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(DEPARTMENTS),
			"in_standard_filter": 1,
			"insert_after": "custom_familia",
		},
	]
	previous = "custom_departamento"
	for attribute, fieldname in ATTRIBUTE_FIELDS.items():
		field = {
			"fieldname": fieldname,
			"label": attribute,
			"fieldtype": "Autocomplete",
			"search_index": 1,
			"insert_after": previous,
		}
		depends_on = shown_for(attribute)
		if depends_on:
			field["depends_on"] = depends_on
		if attribute == "Color":
			field["in_standard_filter"] = 1
		fields.append(field)
		previous = fieldname
	fields += [
		{
			"fieldname": "custom_clasificacion_col",
			"fieldtype": "Column Break",
			"insert_after": previous,
		},
		{
			"fieldname": "custom_es_pack",
			"label": "Es pack",
			"fieldtype": "Check",
			"insert_after": "custom_clasificacion_col",
		},
		{
			"fieldname": "custom_sku_proveedor",
			"label": "SKU proveedor",
			"fieldtype": "Data",
			"search_index": 1,
			"insert_after": "custom_es_pack",
		},
		{
			"fieldname": "custom_brand_supplier",
			"label": "Proveedor de marca",
			"fieldtype": "Link",
			"options": "Supplier",
			"insert_after": "custom_sku_proveedor",
			"description": "Distribuidor de esta marca para este producto. Colecciones distintas = productos distintos (ej. MK Outlet vs MK Tienda).",
		},
		{
			# Its only field moved into Clasificación; the empty section stays hidden.
			"fieldname": "custom_encargo_section",
			"label": "Origen Marca / Proveedor",
			"fieldtype": "Section Break",
			"insert_after": "brand",
			"collapsible": 1,
			"hidden": 1,
		},
	]
	create_custom_fields({"Item": fields}, ignore_validate=True, update=True)


def apply_permissions():
	"""Seller reads the lists and the tree; only the administrator maintains them."""
	for doctype in ("Item Attribute", "Item Group"):
		if frappe.db.exists("Role", SELLER_ROLE):
			_ensure(doctype, SELLER_ROLE, ("read", "select"))
		_ensure(doctype, ADMIN_ROLE, ADMIN_PTYPES)


def _ensure(doctype, role, ptypes):
	if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		add_permission(doctype, role, 0)
	for ptype in ptypes:
		update_permission_property(doctype, role, 0, ptype, 1)
