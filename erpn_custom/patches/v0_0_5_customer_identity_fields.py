import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Customer": [
				{
					"fieldname": "custom_tax_id_type",
					"label": "Tipo de documento",
					"fieldtype": "Select",
					"options": "RUT\nDNI\nCPF\nPassport",
					"insert_after": "tax_id",
					"in_standard_filter": 1,
					"in_quick_entry": 1,
					"translatable": 0,
				},
				{
					"fieldname": "custom_tax_id_country",
					"label": "País emisor del documento",
					"fieldtype": "Link",
					"options": "Country",
					"insert_after": "custom_tax_id_type",
					"in_standard_filter": 1,
					"in_quick_entry": 1,
				},
				{
					"fieldname": "custom_identity_key",
					"label": "Identity Key",
					"fieldtype": "Data",
					"insert_after": "custom_tax_id_country",
					"read_only": 1,
					"hidden": 1,
					"no_copy": 1,
					"translatable": 0,
				},
			]
		},
		ignore_validate=True,
		update=True,
	)

	_ensure_property_setter(
		doctype="Customer",
		fieldname="tax_id",
		property="label",
		value="Número de documento / Tax ID",
		property_type="Data",
	)
	_ensure_property_setter(
		doctype="Customer",
		fieldname="tax_id",
		property="in_quick_entry",
		value="1",
		property_type="Check",
	)
	_ensure_property_setter(
		doctype="Customer",
		fieldname="tax_id",
		property="in_standard_filter",
		value="1",
		property_type="Check",
	)


def _ensure_property_setter(doctype, fieldname, property, value, property_type):
	name = f"{doctype}-{fieldname}-{property}"
	if frappe.db.exists("Property Setter", name):
		doc = frappe.get_doc("Property Setter", name)
		doc.value = value
		doc.property_type = property_type
		doc.save(ignore_permissions=True)
		return
	frappe.get_doc(
		{
			"doctype": "Property Setter",
			"doctype_or_field": "DocField",
			"doc_type": doctype,
			"field_name": fieldname,
			"property": property,
			"value": value,
			"property_type": property_type,
			"name": name,
		}
	).insert(ignore_permissions=True)
