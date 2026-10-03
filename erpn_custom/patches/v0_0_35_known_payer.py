import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	frappe.reload_doc("chile", "doctype", "known_payer")
	create_custom_fields(
		{
			"Bank Transaction": [
				{
					"fieldname": "custom_known_payer",
					"label": "Pagador conocido",
					"fieldtype": "Link",
					"options": "Known Payer",
					"insert_after": "custom_attribution_rule",
					"read_only": 1,
					"allow_on_submit": 1,
					"no_copy": 1,
				}
			]
		},
		ignore_validate=True,
		update=True,
	)
