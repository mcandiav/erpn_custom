import frappe
from frappe import _

from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS, allowed_attributes
from erpn_custom.catalog.tree import ROOT, family_from_chain
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM


def family_of(item_group):
	chain, current = [], item_group
	while current and current != ROOT and len(chain) < 10:
		chain.append(current)
		current = frappe.db.get_value("Item Group", current, "parent_item_group")
	return family_from_chain(chain)


def validate_item_classification(doc, method=None):
	if not doc.brand and doc.item_code != ENCARGO_PENDIENTE_ITEM:
		frappe.throw(_("Marca es obligatoria."), title=_("Falta la marca"))
	apply_classification(doc)


def apply_classification(doc):
	"""Shared by Item and Encargo: familia from the group, attributes only from its lists."""
	doc.custom_familia = family_of(doc.item_group)
	allowed = allowed_attributes(doc.custom_familia)
	for attribute, fieldname in ATTRIBUTE_FIELDS.items():
		value = doc.get(fieldname)
		if not value:
			continue
		if attribute not in allowed:
			doc.set(fieldname, None)
			continue
		if not frappe.db.exists("Item Attribute Value", {"parent": attribute, "attribute_value": value}):
			frappe.throw(
				_("{0} «{1}» no existe en la lista. Pide al administrador que lo agregue.").format(
					_(attribute), value
				)
			)


@frappe.whitelist()
def get_classification_options(item_group=None, departamento=None):
	"""Familia of the group plus the allowed values per attribute field."""
	frappe.has_permission("Item", "read", throw=True)
	family = family_of(item_group) if item_group else None
	options = {}
	for attribute in allowed_attributes(family):
		rows = frappe.get_all(
			"Item Attribute Value",
			filters={"parent": attribute, "parenttype": "Item Attribute"},
			fields=["attribute_value", "custom_departamento", "custom_familia"],
			order_by="idx asc",
		)
		if attribute == "Talla":
			rows = [row for row in rows if row.custom_familia in (None, "", family)]
			if departamento:
				rows = [row for row in rows if row.custom_departamento in (None, "", departamento)]
		options[ATTRIBUTE_FIELDS[attribute]] = [row.attribute_value for row in rows]
	return {"familia": family, "options": options}
