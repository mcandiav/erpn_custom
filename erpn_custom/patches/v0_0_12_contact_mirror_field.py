from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Contact": [
				{
					"fieldname": "custom_is_customer_mirror",
					"label": "Customer Mirror",
					"fieldtype": "Check",
					"insert_after": "is_primary_contact",
					"default": "0",
					"read_only": 1,
					"no_copy": 1,
					"description": "Contacto espejo gestionado desde Customer Individual (B2C).",
				}
			]
		},
		ignore_validate=True,
		update=True,
	)
