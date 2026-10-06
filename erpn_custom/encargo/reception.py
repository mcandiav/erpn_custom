import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM

RECEPTOR_ROLE = "FRAreceptor"
ALLOWED_ROLES = (RECEPTOR_ROLE, "System Manager")
OPEN_RECEPTION = ("PENDING", "RECEIVED")
CODE_MAX = 140

CARD_FIELDS = [
	"name",
	"sales_order",
	"customer",
	"description",
	"brand",
	"supplier",
	"item_group",
	"custom_departamento",
	"custom_color",
	"custom_talla",
	"custom_taco",
	"custom_manga",
	"custom_tamano",
	"custom_tono",
	"custom_contenido",
	"model",
	"notes",
	"reference_url",
	"reference_image",
	"requested_qty",
	"source_type",
	"expected_item",
	"purchase_status",
	"shopper_user",
	"purchased_on",
	"purchase_supplier",
	"proposed_supplier_name",
	"purchase_barcode",
	"purchase_price",
	"purchase_product_image",
	"purchase_label_image",
	"reception_status",
	"received_on",
	"received_by",
	"resolved_item",
	"resolved_by",
]
LOCK_FIELDS = [
	"name",
	"status",
	"purchase_status",
	"reception_status",
	"received_by",
	"resolved_item",
	"source_type",
	"expected_item",
	"shopper_user",
	"purchased_on",
	"purchase_supplier",
	"proposed_supplier_name",
	"purchase_barcode",
	"purchase_price",
	"purchase_product_image",
	"purchase_label_image",
]
# Annulling a wrong purchase sends the Encargo back to the shopper list; the evidence moves to the event log.
PURCHASE_RESET = {
	"purchase_status": "PENDING",
	"shopper_user": None,
	"purchased_on": None,
	"purchase_supplier": None,
	"proposed_supplier_name": None,
	"purchase_barcode": None,
	"purchase_price": 0,
	"purchase_product_image": None,
	"purchase_label_image": None,
	"reception_status": "PENDING",
	"received_on": None,
	"received_by": None,
	"resolved_item": None,
	"resolved_by": None,
}
EVIDENCE_FIELDS = (
	"shopper_user",
	"purchased_on",
	"purchase_supplier",
	"proposed_supplier_name",
	"purchase_barcode",
	"purchase_price",
	"purchase_product_image",
	"purchase_label_image",
)


def is_receptor(roles):
	return bool(set(ALLOWED_ROLES) & set(roles))


def _require_receptor():
	if not is_receptor(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def clean_code(value):
	"""The scanned value is opaque (EAN, UPC, QR, URL...): only the scanner's edge spaces are removed."""
	return (value or "").strip()[:CODE_MAX]


def exact_matches(rows, code, field="purchase_barcode"):
	"""The database collation ignores case; short QR links do not, so the final comparison is exact."""
	return [row for row in rows if (row.get(field) or "") == code]


def _purchase_order_key(row):
	return (str(row.get("purchased_on") or ""), row.get("name") or "")


def pick_candidate(rows):
	"""Unit goes to the oldest purchase still waiting for reception (Spec 013 §34.15, option B)."""
	pending = sorted((row for row in rows if row.get("reception_status") == "PENDING"), key=_purchase_order_key)
	return pending[0] if pending else None


def _require_purchased(row):
	if not row:
		frappe.throw(_("Encargo no encontrado."))
	if row.get("status") != "Open" or row.get("purchase_status") != "PURCHASED":
		frappe.throw(_("El Encargo {0} no está comprado: no se puede recibir.").format(row.get("name")))


def receive_decision(row, user):
	"""'receive' for a purchased unit; 'already_done' for the same receptor's retry."""
	_require_purchased(row)
	status = row.get("reception_status")
	if status == "PENDING":
		return "receive"
	if status == "RECEIVED":
		if row.get("received_by") == user:
			return "already_done"
		frappe.throw(
			_("El Encargo {0} ya fue apartado por {1}. Escanea de nuevo la unidad.").format(
				row.get("name"), row.get("received_by")
			)
		)
	frappe.throw(_("El Encargo {0} ya está resuelto.").format(row.get("name")))


def resolve_decision(row, item_code):
	"""'resolve' for a received unit; 'already_done' for the same resolution repeated."""
	if row and row.get("reception_status") == "RESOLVED_TO_ENC":
		if row.get("resolved_item") == item_code:
			return "already_done"
		frappe.throw(
			_("El Encargo {0} ya fue resuelto con el Item {1}.").format(row.get("name"), row.get("resolved_item"))
		)
	require_received(row)
	return "resolve"


def require_received(row):
	_require_purchased(row)
	if row.get("reception_status") != "RECEIVED":
		frappe.throw(_("Primero aparta la unidad del Encargo {0}.").format(row.get("name")))


def require_valid_item(item):
	if not item:
		frappe.throw(_("Elige un Item válido."))
	if item.get("name") == ENCARGO_PENDIENTE_ITEM:
		frappe.throw(_("{0} es técnico: elige el Item real.").format(ENCARGO_PENDIENTE_ITEM))
	if cint(item.get("disabled")):
		frappe.throw(_("El Item {0} está deshabilitado.").format(item.get("name")))
	if cint(item.get("has_variants")):
		frappe.throw(_("El Item {0} es una plantilla: elige la variante.").format(item.get("name")))


def require_mismatch_confirmed(row, item_code, confirm_mismatch):
	expected = row.get("expected_item")
	if row.get("source_type") == "KNOWN_ITEM" and expected and expected != item_code and not cint(confirm_mismatch):
		frappe.throw(
			_("La venta pidió {0} y elegiste {1}. Confirma que el producto recibido satisface el Encargo.").format(
				expected, item_code
			),
			title=_("Item distinto al vendido"),
		)


def barcode_link_decision(owner, item_code):
	"""A master code identifies a single Item."""
	if not owner:
		return "add"
	if owner == item_code:
		return "already_done"
	frappe.throw(_("El código ya pertenece al Item {0}: no puede identificar dos Items.").format(owner))


def evidence_snapshot(row):
	return {field: row.get(field) for field in EVIDENCE_FIELDS}


def _lock(encargo):
	return frappe.db.get_value("Encargo", encargo, LOCK_FIELDS, as_dict=True, for_update=True)


def _item(item_code):
	if not item_code:
		return None
	return frappe.db.get_value("Item", item_code, ["name", "disabled", "has_variants"], as_dict=True)


def _barcode_owner(code):
	if not code:
		return None
	rows = frappe.get_all("Item Barcode", filters={"barcode": code}, fields=["parent", "barcode"])
	matches = exact_matches(rows, code, "barcode")
	return matches[0].parent if matches else None


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


def _link_code(item_code, code):
	if barcode_link_decision(_barcode_owner(code), item_code) == "already_done":
		return
	frappe.db.get_value("Item", item_code, "name", for_update=True)
	item = frappe.get_doc("Item", item_code)
	item.append("barcodes", {"barcode": code})
	item.flags.ignore_permissions = True
	item.save()


def _card(row):
	return {field: row.get(field) for field in CARD_FIELDS}


@frappe.whitelist()
def find_candidates(code):
	"""First lookup is the Encargo purchase barcode; the Item barcode only helps resolution."""
	_require_receptor()
	code = clean_code(code)
	if not code:
		frappe.throw(_("Escanea o escribe un código."))
	rows = frappe.get_all(
		"Encargo",
		filters={
			"status": "Open",
			"purchase_status": "PURCHASED",
			"purchase_barcode": code,
			"reception_status": ("in", OPEN_RECEPTION),
		},
		fields=CARD_FIELDS,
	)
	rows = exact_matches(rows, code)
	candidate = pick_candidate(rows)
	received = sorted((row for row in rows if row.reception_status == "RECEIVED"), key=_purchase_order_key)
	if candidate:
		match = "encargo"
	elif received:
		match = "received"
	else:
		match = "none"
	return {
		"code": code,
		"match": match,
		"encargo": _card(candidate) if candidate else None,
		"pending_count": sum(1 for row in rows if row.reception_status == "PENDING"),
		"received": [_card(row) for row in received],
		"item": _barcode_owner(code),
	}


@frappe.whitelist()
def get_case(encargo):
	_require_receptor()
	row = frappe.db.get_value("Encargo", encargo, CARD_FIELDS, as_dict=True)
	if not row:
		frappe.throw(_("Encargo no encontrado."))
	return {"encargo": _card(row), "item": _barcode_owner(row.purchase_barcode)}


@frappe.whitelist()
def list_reception(search=None, reception_status="PENDING", limit=100):
	"""Purchased Encargos waiting for reception plus the latest received/resolved ones."""
	_require_receptor()
	filters = {"status": "Open", "purchase_status": "PURCHASED"}
	if reception_status in ("PENDING", "RECEIVED", "RESOLVED_TO_ENC"):
		filters["reception_status"] = reception_status
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
			"purchase_supplier": ("like", like),
			"proposed_supplier_name": ("like", like),
		}
	order_by = "purchased_on asc" if reception_status == "PENDING" else "modified desc"
	return frappe.get_all(
		"Encargo",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"sales_order",
			"customer",
			"brand",
			"description",
			"purchased_on",
			"purchase_supplier",
			"proposed_supplier_name",
			"shopper_user",
			"purchase_barcode",
			"reception_status",
			"received_on",
			"received_by",
		],
		order_by=order_by,
		limit_page_length=min(cint(limit) or 100, 500),
	)


@frappe.whitelist(methods=["POST"])
def mark_received(encargo, code=None):
	"""APARTADO / CONTINUAR: physical reception; the Item is resolved later."""
	_require_receptor()
	user = frappe.session.user
	row = _lock(encargo)
	if receive_decision(row, user) == "already_done":
		return {"encargo": encargo, "reception_status": "RECEIVED"}
	frappe.db.set_value(
		"Encargo",
		encargo,
		{"reception_status": "RECEIVED", "received_on": now_datetime(), "received_by": user},
		update_modified=True,
	)
	_log(encargo, "RECEIVED", scanned_code=clean_code(code) or None)
	return {"encargo": encargo, "reception_status": "RECEIVED"}


@frappe.whitelist(methods=["POST"])
def not_matching(encargo, code=None, notes=None):
	"""NO CORRESPONDE: auditable scan, no state change."""
	_require_receptor()
	if not frappe.db.exists("Encargo", encargo):
		frappe.throw(_("Encargo no encontrado."))
	_log(encargo, "NOT_MATCHING", scanned_code=clean_code(code) or None, notes=(notes or "").strip()[:1000] or None)
	return {"encargo": encargo}


@frappe.whitelist(methods=["POST"])
def resolve_to_encargo(encargo, item_code, link_code=0, confirm_mismatch=0):
	"""SATISFACE ENCARGO. The submitted Sales Order is not rewritten."""
	_require_receptor()
	row = _lock(encargo)
	if resolve_decision(row, item_code) == "already_done":
		return {"encargo": encargo, "reception_status": "RESOLVED_TO_ENC", "resolved_item": item_code}
	require_valid_item(_item(item_code))
	require_mismatch_confirmed(row, item_code, confirm_mismatch)
	if cint(link_code) and row.purchase_barcode:
		_link_code(item_code, row.purchase_barcode)
	frappe.db.set_value(
		"Encargo",
		encargo,
		{"resolved_item": item_code, "resolved_by": frappe.session.user, "reception_status": "RESOLVED_TO_ENC"},
		update_modified=True,
	)
	_log(encargo, "RESOLVED_TO_ENC", item=item_code, scanned_code=row.purchase_barcode)
	return {"encargo": encargo, "reception_status": "RESOLVED_TO_ENC", "resolved_item": item_code}


@frappe.whitelist(methods=["POST"])
def annul_purchase(encargo, item_code, link_code=0, notes=None):
	"""ANULAR COMPRA / ITEM A STOCK: the wrong unit goes to normal stock and the Encargo returns to the shopper."""
	_require_receptor()
	row = _lock(encargo)
	require_received(row)
	require_valid_item(_item(item_code))
	if cint(link_code) and row.purchase_barcode:
		_link_code(item_code, row.purchase_barcode)
	evidence = evidence_snapshot(row)
	evidence["purchase_price"] = flt(evidence.get("purchase_price"), 2)
	_log(
		encargo,
		"PURCHASE_ANNULLED",
		item=item_code,
		scanned_code=row.purchase_barcode,
		notes=(notes or "").strip()[:1000] or None,
		**evidence,
	)
	frappe.db.set_value("Encargo", encargo, PURCHASE_RESET, update_modified=True)
	return {"encargo": encargo, "purchase_status": "PENDING", "reception_status": "PENDING"}
