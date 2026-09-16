import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def oauth_callback(code=None, state=None, error=None, error_description=None):
    """OAuth redirect endpoint for Banco de Chile.

    This endpoint is intentionally minimal until Banco de Chile's exact
    authorization-code exchange contract is confirmed from the registered app.
    """
    if error:
        frappe.local.response.http_status_code = 400
        return {
            "ok": False,
            "error": error,
            "error_description": error_description,
        }

    if not code:
        frappe.local.response.http_status_code = 400
        return {"ok": False, "error": _("Missing authorization code")}

    return {
        "ok": True,
        "message": _("Banco de Chile authorization callback received"),
        "state_received": bool(state),
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def notifications_webhook():
    """Receive Banco de Chile transfer notifications.

    After a Bank Transaction is created from a notification, call
    resolve_party_for_ingested_transaction(name) so party uses the same Exact
    Tax ID engine as Pagos de Clientes and the interval job.
    """
    payload = frappe.request.get_json(silent=True) or {}

    return {
        "ok": True,
        "message": _("Banco de Chile notification received"),
        "received": bool(payload),
    }


def resolve_party_for_ingested_transaction(bank_transaction_name):
    """Call the shared Exact Tax ID engine after a Bank Transaction is created."""
    from erpn_custom.chile.deposit_mapping import apply_party_for_bank_transaction

    return apply_party_for_bank_transaction(bank_transaction_name)
