from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Shipment": [
				{
					"fieldname": "custom_courier_section",
					"label": "Courier Integration",
					"fieldtype": "Section Break",
					"insert_after": "amended_from",
					"collapsible": 1,
				},
				{
					"fieldname": "custom_courier_configuration",
					"label": "Courier Configuration",
					"fieldtype": "Link",
					"options": "Courier Configuration",
					"insert_after": "custom_courier_section",
					"allow_on_submit": 1,
					"in_standard_filter": 1,
				},
				{
					"fieldname": "custom_courier_environment",
					"label": "Courier Environment",
					"fieldtype": "Data",
					"insert_after": "custom_courier_configuration",
					"read_only": 1,
					"fetch_from": "custom_courier_configuration.environment",
					"allow_on_submit": 1,
				},
				{
					"fieldname": "custom_courier_service_code",
					"label": "Courier Service Code",
					"fieldtype": "Data",
					"insert_after": "custom_courier_environment",
					"allow_on_submit": 1,
					"no_copy": 1,
				},
				{
					"fieldname": "custom_courier_column_break",
					"fieldtype": "Column Break",
					"insert_after": "custom_courier_service_code",
				},
				{
					"fieldname": "custom_courier_creation_state",
					"label": "Courier Creation State",
					"fieldtype": "Select",
					"options": "Not Requested\nCreating\nCreated\nUncertain\nFailed",
					"default": "Not Requested",
					"insert_after": "custom_courier_column_break",
					"allow_on_submit": 1,
					"no_copy": 1,
					"read_only": 1,
				},
				{
					"fieldname": "custom_courier_creation_key",
					"label": "Courier Creation Key",
					"fieldtype": "Data",
					"insert_after": "custom_courier_creation_state",
					"allow_on_submit": 1,
					"no_copy": 1,
					"read_only": 1,
				},
				{
					"fieldname": "custom_courier_created_at",
					"label": "Courier Created At",
					"fieldtype": "Datetime",
					"insert_after": "custom_courier_creation_key",
					"allow_on_submit": 1,
					"no_copy": 1,
					"read_only": 1,
				},
				{
					"fieldname": "custom_last_tracking_at",
					"label": "Last Tracking At",
					"fieldtype": "Datetime",
					"insert_after": "custom_courier_created_at",
					"allow_on_submit": 1,
					"no_copy": 1,
					"read_only": 1,
				},
			]
		},
		ignore_validate=True,
		update=True,
	)
