from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Bank Transaction": [
				{
					"fieldname": "custom_fecha_y_hora_bancaria",
					"label": "Fecha y hora bancaria",
					"fieldtype": "Datetime",
					"insert_after": "date",
					"allow_on_submit": 1,
				},
				{
					"fieldname": "custom_rut_del_pagador",
					"label": "RUT del pagador",
					"fieldtype": "Data",
					"insert_after": "bank_party_name",
					"allow_on_submit": 1,
					"translatable": 0,
				},
				{
					"fieldname": "custom_banco_origen",
					"label": "Banco origen",
					"fieldtype": "Data",
					"insert_after": "custom_rut_del_pagador",
					"allow_on_submit": 1,
					"translatable": 0,
				},
				{
					"fieldname": "custom_cuenta_destino",
					"label": "Cuenta destino",
					"fieldtype": "Data",
					"insert_after": "bank_party_account_number",
					"allow_on_submit": 1,
					"translatable": 0,
				},
				{
					"fieldname": "custom_tipo_operador",
					"label": "Tipo Operador",
					"fieldtype": "Data",
					"insert_after": "transaction_type",
					"allow_on_submit": 1,
					"translatable": 0,
				},
			],
			"Bank Statement Import": [
				{
					"fieldname": "custom_banco_chile_import_result",
					"label": "Resultado importacion Banco de Chile",
					"fieldtype": "Code",
					"options": "JSON",
					"insert_after": "template_warnings",
					"read_only": 1,
				},
			],
		},
		ignore_validate=True,
		update=True,
	)
