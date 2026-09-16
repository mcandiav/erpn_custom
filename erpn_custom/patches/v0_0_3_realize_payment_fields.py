from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Bank Transaction": [
				{
					"fieldname": "custom_payment_entry",
					"label": "Payment Entry",
					"fieldtype": "Link",
					"options": "Payment Entry",
					"insert_after": "custom_ingest_status",
					"read_only": 1,
					"allow_on_submit": 1,
				},
				{
					"fieldname": "custom_realization_status",
					"label": "Realization Status",
					"fieldtype": "Select",
					"options": "\nPending\nRealized\nSkipped\nError",
					"insert_after": "custom_payment_entry",
					"read_only": 1,
					"allow_on_submit": 1,
				},
				{
					"fieldname": "custom_realization_error",
					"label": "Realization Error",
					"fieldtype": "Small Text",
					"insert_after": "custom_realization_status",
					"read_only": 1,
					"allow_on_submit": 1,
				},
			],
			"Payment Entry": [
				{
					"fieldname": "custom_bank_transaction",
					"label": "Bank Transaction",
					"fieldtype": "Link",
					"options": "Bank Transaction",
					"insert_after": "reference_date",
					"read_only": 1,
					"allow_on_submit": 1,
				},
				{
					"fieldname": "custom_ingest_key",
					"label": "Ingest Key",
					"fieldtype": "Data",
					"insert_after": "custom_bank_transaction",
					"read_only": 1,
					"allow_on_submit": 1,
					"translatable": 0,
				},
			],
		},
		ignore_validate=True,
		update=True,
	)
