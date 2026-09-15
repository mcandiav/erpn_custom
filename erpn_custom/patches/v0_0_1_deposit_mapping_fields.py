from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Bank Transaction": [
                {
                    "fieldname": "custom_rut_pagador_normalizado",
                    "label": "RUT Pagador Normalizado",
                    "fieldtype": "Data",
                    "insert_after": "custom_rut_del_pagador",
                    "read_only": 1,
                    "allow_on_submit": 1,
                    "translatable": 0,
                },
                {
                    "fieldname": "custom_attribution_rule",
                    "label": "Attribution Rule",
                    "fieldtype": "Data",
                    "insert_after": "custom_rut_pagador_normalizado",
                    "read_only": 1,
                    "allow_on_submit": 1,
                    "translatable": 0,
                },
                {
                    "fieldname": "custom_attribution_run",
                    "label": "Attribution Run",
                    "fieldtype": "Link",
                    "options": "Deposit Mapping Run",
                    "insert_after": "custom_attribution_rule",
                    "read_only": 1,
                    "allow_on_submit": 1,
                },
                {
                    "fieldname": "custom_mapping_status",
                    "label": "Mapping Status",
                    "fieldtype": "Select",
                    "options": "\nNo Match\nConflict\nError\nMapped",
                    "insert_after": "custom_attribution_run",
                    "read_only": 1,
                    "allow_on_submit": 1,
                },
            ]
        },
        ignore_validate=True,
        update=True,
    )
