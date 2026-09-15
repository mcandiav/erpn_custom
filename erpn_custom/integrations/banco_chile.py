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

    Raw payload processing, signature validation, idempotency and creation of
    ERPNext Bank Transaction/Payment Entry records will be added after the
    sandbox contract and sample payload are confirmed.
    """
    payload = frappe.request.get_json(silent=True) or {}

    return {
        "ok": True,
        "message": _("Banco de Chile notification received"),
        "received": bool(payload),
    }
