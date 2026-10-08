from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"User": [
				{
					"fieldname": "custom_shopper_currency",
					"label": "Moneda de compra Shopper",
					"fieldtype": "Link",
					"options": "Currency",
					"insert_after": "language",
					"description": "Moneda en que este Shopper registra sus compras. Vacío = USD.",
				}
			]
		},
		ignore_validate=True,
		update=True,
	)
