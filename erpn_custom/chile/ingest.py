def make_ingest_key(bank_account, transaction_id):
    account = (bank_account or "").strip()
    tid = (transaction_id or "").strip()
    if not account or not tid:
        return None
    return f"{account}|{tid}"


def decide_ingest(bank_account, transaction_id, existing_names):
    if not (transaction_id or "").strip():
        return "reject_missing_transaction_id"
    if not (bank_account or "").strip():
        return "reject_missing_bank_account"
    if existing_names:
        return "skip_duplicate"
    return "create"


def validate_ingest(doc, method=None):
    import frappe
    from frappe import _

    if not doc.is_new():
        return

    existing = _existing_names(doc.bank_account, doc.transaction_id, exclude_name=doc.name)
    decision = decide_ingest(doc.bank_account, doc.transaction_id, existing)

    if decision == "reject_missing_transaction_id":
        frappe.throw(_("transaction_id is required; ingest rejected"))
    if decision == "reject_missing_bank_account":
        frappe.throw(_("bank_account is required; ingest rejected"))
    if decision == "skip_duplicate":
        frappe.throw(
            _("duplicate/skipped: Bank Transaction {0} already exists for bank_account + transaction_id").format(
                existing[0]
            )
        )

    doc.custom_ingest_key = make_ingest_key(doc.bank_account, doc.transaction_id)
    doc.custom_ingest_status = "Ingested"


def _existing_names(bank_account, transaction_id, exclude_name=None):
    import frappe

    key = make_ingest_key(bank_account, transaction_id)
    if not key:
        return []
    names = frappe.get_all(
        "Bank Transaction",
        filters={
            "bank_account": (bank_account or "").strip(),
            "transaction_id": (transaction_id or "").strip(),
            "docstatus": ["<", 2],
        },
        pluck="name",
        order_by="creation asc, name asc",
    )
    if exclude_name:
        names = [name for name in names if name != exclude_name]
    return names
