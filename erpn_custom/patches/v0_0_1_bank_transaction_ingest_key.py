import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpn_custom.chile.ingest import make_ingest_key


def execute():
    create_custom_fields(
        {
            "Bank Transaction": [
                {
                    "fieldname": "custom_ingest_key",
                    "label": "Ingest Key",
                    "fieldtype": "Data",
                    "insert_after": "custom_mapping_status",
                    "read_only": 1,
                    "allow_on_submit": 1,
                    "translatable": 0,
                    "unique": 0,
                },
                {
                    "fieldname": "custom_ingest_status",
                    "label": "Ingest Status",
                    "fieldtype": "Select",
                    "options": "\nIngested\nDuplicate",
                    "insert_after": "custom_ingest_key",
                    "read_only": 1,
                    "allow_on_submit": 1,
                },
            ]
        },
        ignore_validate=True,
        update=True,
    )
    _backfill_existing()
    _ensure_unique_ingest_key()


def _backfill_existing():
    rows = frappe.get_all(
        "Bank Transaction",
        fields=["name", "bank_account", "transaction_id"],
        filters={"docstatus": ["<", 2]},
        order_by="creation asc, name asc",
    )
    seen = {}
    for row in rows:
        key = make_ingest_key(row.bank_account, row.transaction_id)
        if not key:
            frappe.db.set_value(
                "Bank Transaction",
                row.name,
                {"custom_ingest_key": None, "custom_ingest_status": ""},
                update_modified=False,
            )
            continue
        if key in seen:
            frappe.db.set_value(
                "Bank Transaction",
                row.name,
                {"custom_ingest_key": None, "custom_ingest_status": "Duplicate"},
                update_modified=False,
            )
            continue
        seen[key] = row.name
        frappe.db.set_value(
            "Bank Transaction",
            row.name,
            {"custom_ingest_key": key, "custom_ingest_status": "Ingested"},
            update_modified=False,
        )
    frappe.db.sql(
        """
        UPDATE `tabBank Transaction`
        SET custom_ingest_key = NULL
        WHERE IFNULL(custom_ingest_key, '') = '' OR custom_ingest_status = 'Duplicate'
        """
    )


def _ensure_unique_ingest_key():
    fieldname = frappe.db.get_value(
        "Custom Field",
        {"dt": "Bank Transaction", "fieldname": "custom_ingest_key"},
        "name",
    )
    if not fieldname:
        return
    doc = frappe.get_doc("Custom Field", fieldname)
    if not doc.unique:
        doc.unique = 1
        doc.save(ignore_permissions=True)
