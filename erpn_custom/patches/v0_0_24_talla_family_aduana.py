import frappe

from erpn_custom.catalog.aduana import apply_aduana_seed
from erpn_custom.catalog.provision import apply_attribute_value_fields, apply_attributes


def execute():
	if not frappe.db.exists("Module Def", "Catalog"):
		frappe.get_doc({"doctype": "Module Def", "module_name": "Catalog", "app_name": "erpn_custom"}).insert(
			ignore_permissions=True
		)
	frappe.reload_doc("catalog", "doctype", "diccionario_aduana")
	apply_attribute_value_fields()
	apply_attributes()
	apply_aduana_seed()
