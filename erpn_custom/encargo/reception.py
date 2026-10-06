import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime

RECEPTOR_ROLE = "FRAreceptor"
ALLOWED_ROLES = (RECEPTOR_ROLE, "System Manager")
# The shopper already matched the product to the Encargo; a wrong purchase is handled by sales.
RETURN_ROLES = ("ComercialFRA", "System Manager")
CODE_MAX = 140
NOTES_MAX = 1000

CARD_FIELDS = [
	"name",
	"sales_order",
	"customer",
	"description",
	"brand",
	"purchase_barcode",
	"purchased_on",
	"purchase_supplier",
	"proposed_supplier_name",
	"reception_status",
	"received_on",
	"received_by",
]
LOCK_FIELDS = ["name", "status", "purchase_status", "reception_status", "purchase_barcode"]


def is_receptor(roles):
	return bool(set(ALLOWED_ROLES) & set(roles))


def can_return_to_stock(roles):
	return bool(set(RETURN_ROLES) & set(roles))


def _require(allowed):
	if not allowed(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def clean_code(value):
	"""The scanned value is opaque (EAN, UPC, QR, URL...): only the scanner's edge spaces are removed."""
	return (value or "").strip()[:CODE_MAX]


def clean_notes(value):
	return (value or "").strip()[:NOTES_MAX]


def exact_matches(rows, code, field="purchase_barcode"):
	"""The database collation ignores case; short QR links do not, so the final comparison is exact."""
	return [row for row in rows if (row.get(field) or "") == code]


def _purchase_order_key(row):
	return (str(row.get("purchased_on") or ""), row.get("name") or "")


def oldest_first(rows):
	"""Each unit goes to the oldest purchase still waiting for reception (Spec 013 §34.20, option B)."""
	return sorted(rows, key=_purchase_order_key)


def is_receivable(row):
	return bool(
		row
		and row.get("status") == "Open"
		and row.get("purchase_status") == "PURCHASED"
		and row.get("reception_status") == "PENDING"
	)


def return_decision(row):
	"""'return' for a received unit; 'already_done' when sales already sent it to stock."""
	if not row:
		frappe.throw(_("Encargo no encontrado."))
	status = row.get("reception_status")
	if status == "RESOLVED_TO_STOCK":
		return "already_done"
	if row.get("status") != "Open" or row.get("purchase_status") != "PURCHASED" or status != "RECEIVED":
		frappe.throw(_("El Encargo {0} no está recibido: no se puede devolver a stock.").format(row.get("name")))
	return "return"


def _lock(encargo):
	return frappe.db.get_value("Encargo", encargo, LOCK_FIELDS, as_dict=True, for_update=True)


def _log(encargo, action, **values):
	count = frappe.db.count("Encargo Reception Event", {"parent": encargo})
	frappe.get_doc(
		{
			"doctype": "Encargo Reception Event",
			"name": frappe.generate_hash(length=10),
			"parent": encargo,
			"parenttype": "Encargo",
			"parentfield": "reception_events",
			"idx": count + 1,
			"action": action,
			"event_on": now_datetime(),
			"user": frappe.session.user,
			**values,
		}
	).db_insert()


def _card(encargo):
	return frappe.db.get_value("Encargo", encargo, CARD_FIELDS, as_dict=True)


@frappe.whitelist(methods=["POST"])
def receive_scan(code):
	"""One scan = one unit: it is received by the oldest pending Encargo with that code, otherwise it is stock."""
	_require(is_receptor)
	code = clean_code(code)
	if not code:
		frappe.throw(_("Escanea o escribe un código."))
	rows = frappe.get_all(
		"Encargo",
		filters={
			"status": "Open",
			"purchase_status": "PURCHASED",
			"reception_status": "PENDING",
			"purchase_barcode": code,
		},
		fields=["name", "purchased_on", "purchase_barcode"],
	)
	candidates = oldest_first(exact_matches(rows, code))
	for index, candidate in enumerate(candidates):
		# Another receptor may have taken this unit between the search and the lock.
		if not is_receivable(_lock(candidate.name)):
			continue
		frappe.db.set_value(
			"Encargo",
			candidate.name,
			{"reception_status": "RECEIVED", "received_on": now_datetime(), "received_by": frappe.session.user},
			update_modified=True,
		)
		_log(candidate.name, "RECEIVED", scanned_code=code)
		return {
			"match": "encargo",
			"code": code,
			"encargo": _card(candidate.name),
			"pending_left": len(candidates) - index - 1,
		}
	return {"match": "stock", "code": code}


@frappe.whitelist()
def list_reception(view="pending", search=None, limit=100):
	"""Read-only lists for the receptor: purchased but not received, and received today."""
	_require(is_receptor)
	filters = {"status": "Open", "purchase_status": "PURCHASED"}
	if view == "today":
		filters["reception_status"] = "RECEIVED"
		filters["received_on"] = (">=", getdate())
		order_by = "received_on desc"
	else:
		filters["reception_status"] = "PENDING"
		order_by = "purchased_on asc"
	or_filters = None
	text = (search or "").strip()
	if text:
		like = f"%{text}%"
		or_filters = {
			"name": ("like", like),
			"sales_order": ("like", like),
			"customer": ("like", like),
			"brand": ("like", like),
			"description": ("like", like),
			"purchase_barcode": ("like", like),
		}
	return frappe.get_all(
		"Encargo",
		filters=filters,
		or_filters=or_filters,
		fields=CARD_FIELDS,
		order_by=order_by,
		limit_page_length=min(cint(limit) or 100, 500),
	)


@frappe.whitelist(methods=["POST"])
def return_to_stock(encargo, notes=None):
	"""DEVOLVER A STOCK: the received unit becomes normal stock; sales cancels the order line separately."""
	_require(can_return_to_stock)
	notes = clean_notes(notes)
	if not notes:
		frappe.throw(_("Indica el motivo de la devolución a stock."))
	row = _lock(encargo)
	if return_decision(row) == "already_done":
		return {"encargo": encargo, "reception_status": "RESOLVED_TO_STOCK"}
	frappe.db.set_value(
		"Encargo",
		encargo,
		{"reception_status": "RESOLVED_TO_STOCK", "resolved_by": frappe.session.user},
		update_modified=True,
	)
	_log(encargo, "RETURNED_TO_STOCK", scanned_code=row.purchase_barcode, notes=notes)
	return {"encargo": encargo, "reception_status": "RESOLVED_TO_STOCK"}
