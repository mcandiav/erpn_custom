import base64
import re
from datetime import timedelta
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import cint, flt, get_url, now_datetime

from erpn_custom.encargo import barcode_exception, demand, inventory

SHOPPER_ROLE = "ShopperFRA"
ALLOWED_ROLES = (SHOPPER_ROLE, "System Manager")
REVIEW_AFTER_NOT_FOUND = 3
ALL_PLACES = "TODOS"

# Never add customer, sales order, sale rate or seller: the shopper must not see them.
# reference_url is only sent through reference_link(), which drops links into this ERP.
LIST_FIELDS = [
	"name",
	"description",
	"brand",
	"supplier",
	"item_group",
	"custom_familia",
	"custom_departamento",
	"custom_color",
	"custom_talla",
	"custom_taco",
	"custom_manga",
	"custom_tamano",
	"custom_tono",
	"custom_contenido",
	"model",
	"size",
	"color",
	"requested_qty",
	"sourced_qty",
	"pending_supply_qty",
	"reference_url",
	"notes",
	"reference_image",
	"not_found_count",
	"needs_commercial_review",
	"creation",
]
ATTRIBUTE_LABELS = (
	("custom_color", "Color"),
	("custom_talla", "Talla"),
	("custom_taco", "Taco"),
	("custom_manga", "Manga"),
	("custom_tamano", "Tamaño"),
	("custom_tono", "Tono"),
	("custom_contenido", "Contenido"),
)
EVENT_FIELDS = [
	"name",
	"parent",
	"qty",
	"status",
	"purchased_on",
	"purchase_price",
	"purchase_currency",
	"purchase_barcode",
	"supplier",
	"proposed_supplier_name",
	"purchase_product_image",
	"purchase_label_image",
	"barcode_exception_status",
]
IMAGE_FIELDS = {
	"reference": "reference_image",
	"product": "purchase_product_image",
	"label": "purchase_label_image",
}
LOCK_FIELDS = ["name", "status", "requested_qty", "pending_supply_qty", "not_found_count"]
URL_SCHEME = re.compile(r"^https?://", re.I)
BARE_DOMAIN = re.compile(r"^[^\s/]+\.[a-z]{2,}(/\S*)?$", re.I)
IMAGE_DATA_URL = re.compile(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$", re.S)


def is_shopper(roles):
	return bool(set(ALLOWED_ROLES) & set(roles))


def _require_shopper():
	if not is_shopper(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def missing_evidence(barcode, product_image, label_image, price):
	missing = []
	if not (barcode or "").strip():
		missing.append(_("barcode"))
	if not product_image:
		missing.append(_("foto del producto"))
	if not label_image:
		missing.append(_("foto de etiqueta"))
	if flt(price) <= 0:
		missing.append(_("precio"))
	return missing


def needs_review(not_found_count):
	return cint(not_found_count) >= REVIEW_AFTER_NOT_FOUND


def reference_link(value, own_host):
	"""(url, text) for the shopper. Links into this ERP (or relative paths) are dropped: they
	expose the sales order and the shopper has no Desk access. Plain text is returned as text."""
	text = (value or "").strip()
	if not text:
		return None, None
	if URL_SCHEME.match(text):
		url = text
	elif BARE_DOMAIN.match(text):
		url = "https://" + text
	else:
		return (None, None) if text.startswith("/") else (None, text)
	host = (urlparse(url).hostname or "").lower()
	if not host or host == (own_host or "").lower():
		return None, None
	return url, None


def _own_host():
	return urlparse(get_url()).hostname


def period_start(period, now):
	"""'all' has no lower bound; '7d' is the last seven days; anything else is today."""
	if period == "all":
		return None
	if period == "7d":
		return now - timedelta(days=7)
	return now.replace(hour=0, minute=0, second=0, microsecond=0)


def can_view_image(row, user, kind, event=None):
	"""Open demand exposes only the reference; a purchase exposes its evidence to its own shopper."""
	if not row or kind not in IMAGE_FIELDS:
		return False
	if event is not None:
		return event.get("shopper_user") == user
	if kind != "reference":
		return False
	return row.get("status") == "Open" and flt(row.get("pending_supply_qty")) > 0


def clean_qty(value):
	"""Whole units only: one physical unit is one quantity of demand (Spec 020 §7)."""
	qty = flt(value)
	if qty <= 0 or qty != int(qty):
		frappe.throw(_("Indica cuántas unidades compraste (número entero mayor que 0)."))
	return int(qty)


def purchase_decision(row, events, user, request_id, qty, pending_supply):
	"""('confirm', None) for a new purchase, ('already_done', event) for a retry of the same request."""
	if not row or row.get("status") != "Open":
		frappe.throw(_("Este Encargo ya no está disponible para compra."))
	if request_id:
		previous = next((e for e in events if e.get("request_id") == request_id), None)
		if previous:
			if previous.get("shopper_user") != user:
				frappe.throw(_("Este Encargo ya no está disponible para compra."))
			return "already_done", previous
	pending_supply = flt(pending_supply)
	if pending_supply <= 0:
		frappe.throw(_("Este Encargo ya fue abastecido completo por otra compra o recepción."))
	if qty > pending_supply:
		frappe.throw(
			_("Solo quedan {0} unidades por comprar en este Encargo.").format(f"{pending_supply:g}"),
			title=_("Cantidad mayor a la pendiente"),
		)
	return "confirm", None


def clean_request_id(value):
	value = (value or "").strip()
	return value[:64] if re.match(r"^[A-Za-z0-9-]{8,64}$", value) else None


def resolve_place(supplier, proposed_supplier_name):
	"""Validated master Supplier, or the typed place name. Never creates a Supplier."""
	supplier = (supplier or "").strip()
	if supplier == ALL_PLACES:
		supplier = ""
	proposed = (proposed_supplier_name or "").strip()[:140]
	if supplier:
		if not frappe.db.exists("Supplier", {"name": supplier, "disabled": 0}):
			frappe.throw(_("El lugar «{0}» no existe en la lista.").format(supplier))
		return supplier, None
	if not proposed:
		frappe.throw(_("Indica dónde estás comprando."))
	return None, proposed


def _lock_pending(encargo):
	row = frappe.db.get_value("Encargo", encargo, LOCK_FIELDS, as_dict=True, for_update=True)
	if not row:
		frappe.throw(_("Encargo no encontrado."))
	return row


def _image_url(encargo, file_url, kind="reference", supply_event=None):
	if not file_url:
		return None
	if file_url.startswith("/private/"):
		url = f"/api/method/erpn_custom.encargo.shopper.reference_image?encargo={encargo}&kind={kind}"
		return f"{url}&supply_event={supply_event}" if supply_event else url
	return file_url


def _variant(row):
	parts = [f"{label}: {row.get(field)}" for field, label in ATTRIBUTE_LABELS if row.get(field)]
	if not parts:
		parts = [value for value in (row.get("size"), row.get("color")) if value]
	return " · ".join(parts)


def _card(row, own_host=None):
	reference_url, reference_text = reference_link(row.reference_url, own_host)
	return {
		"reference_url": reference_url,
		"reference_text": reference_text,
		"name": row.name,
		"description": row.description,
		"brand": row.brand,
		"suggested_supplier": row.supplier,
		"item_group": row.item_group,
		"familia": row.custom_familia,
		"departamento": row.custom_departamento,
		"talla": row.custom_talla or row.custom_tamano or row.size,
		"variant": _variant(row),
		"model": row.model,
		"requested_qty": flt(row.requested_qty),
		"sourced_qty": flt(row.sourced_qty),
		"pending_supply_qty": flt(row.pending_supply_qty),
		"notes": row.notes,
		"image": _image_url(row.name, row.reference_image),
		"not_found_count": cint(row.not_found_count),
		"needs_commercial_review": cint(row.needs_commercial_review),
	}


@frappe.whitelist()
def get_places():
	"""Suppliers with brands (stores). Shopper-type Suppliers carry no brands."""
	_require_shopper()
	return frappe.db.sql(
		"""
		select distinct s.name, s.supplier_name
		from `tabSupplier` s
		inner join `tabSupplier Brand` sb
			on sb.parent = s.name and sb.parenttype = 'Supplier'
		where ifnull(s.disabled, 0) = 0
		order by s.supplier_name, s.name
		""",
		as_dict=True,
	)


@frappe.whitelist()
def list_pending(supplier=None):
	_require_shopper()
	rows = frappe.get_all(
		"Encargo",
		filters={"status": "Open", "pending_supply_qty": (">", 0)},
		fields=LIST_FIELDS,
		order_by="creation asc, name asc",
	)
	if supplier and supplier != ALL_PLACES:
		brands = set(
			frappe.get_all(
				"Supplier Brand",
				filters={"parent": supplier, "parenttype": "Supplier"},
				pluck="brand",
			)
		)
		rows = [row for row in rows if row.supplier == supplier or row.brand in brands]
	own_host = _own_host()
	return [_card(row, own_host) for row in rows]


def _purchase_card(row, event, place_labels, own_host):
	card = _card(row, own_host)
	card.update(
		{
			"supply_event": event.name,
			"image": _image_url(row.name, row.reference_image, "reference", event.name),
			"purchase_qty": flt(event.qty),
			"purchase_status": event.status,
			"barcode_exception_status": event.barcode_exception_status,
			"purchased_on": event.purchased_on,
			"purchase_price": flt(event.purchase_price, 2),
			"purchase_total": flt(flt(event.purchase_price) * flt(event.qty), 2),
			"purchase_barcode": event.purchase_barcode,
			"place": place_labels.get(event.supplier) or event.supplier or event.proposed_supplier_name,
			"product_image": _image_url(row.name, event.purchase_product_image, "product", event.name),
			"label_image": _image_url(row.name, event.purchase_label_image, "label", event.name),
		}
	)
	return card


@frappe.whitelist()
def list_purchased(period="today"):
	"""Only the purchase events of the logged-in shopper; same hidden fields as the pending list."""
	_require_shopper()
	filters = {"parenttype": "Encargo", "source_type": demand.SHOPPER, "shopper_user": frappe.session.user}
	start = period_start(period, now_datetime())
	if start:
		filters["purchased_on"] = (">=", start)
	events = frappe.get_all(demand.EVENT, filters=filters, fields=EVENT_FIELDS, order_by="purchased_on desc")
	encargos = (
		{row.name: row for row in frappe.get_all("Encargo", filters={"name": ("in", list({e.parent for e in events}))}, fields=LIST_FIELDS)}
		if events
		else {}
	)
	suppliers = list({event.supplier for event in events if event.supplier})
	place_labels = (
		dict(frappe.get_all("Supplier", filters={"name": ("in", suppliers)}, fields=["name", "supplier_name"], as_list=True))
		if suppliers
		else {}
	)
	own_host = _own_host()
	rows = [
		_purchase_card(encargos[event.parent], event, place_labels, own_host)
		for event in events
		if event.parent in encargos
	]
	return {
		"rows": rows,
		"count": len(rows),
		"total": flt(sum(row["purchase_total"] for row in rows), 2),
	}


@frappe.whitelist()
def reference_image(encargo, kind="reference", supply_event=None):
	_require_shopper()
	row = frappe.db.get_value("Encargo", encargo, ["status", "pending_supply_qty", "reference_image"], as_dict=True)
	event = None
	if supply_event:
		event = frappe.db.get_value(
			demand.EVENT,
			{"name": supply_event, "parent": encargo, "parenttype": "Encargo"},
			["shopper_user", "purchase_product_image", "purchase_label_image"],
			as_dict=True,
		)
		if not event:
			raise frappe.DoesNotExistError
	source = event if kind != "reference" and event else row
	if not can_view_image(row, frappe.session.user, kind, event) or not (source or {}).get(IMAGE_FIELDS[kind]):
		raise frappe.DoesNotExistError
	file_name = frappe.db.get_value("File", {"file_url": source.get(IMAGE_FIELDS[kind])}, "name")
	if not file_name:
		raise frappe.DoesNotExistError
	file_doc = frappe.get_doc("File", file_name)
	frappe.local.response.filename = file_doc.file_name
	frappe.local.response.filecontent = file_doc.get_content()
	frappe.local.response.type = "download"
	frappe.local.response.display_content_as = "inline"


def decode_image(data_url):
	match = IMAGE_DATA_URL.match((data_url or "").strip())
	if not match:
		return None
	try:
		content = base64.b64decode(match.group(2), validate=True)
	except ValueError:
		return None
	ext = "jpg" if match.group(1) in ("jpeg", "jpg") else match.group(1)
	return content, ext


def _save_evidence(encargo, fieldname, content, ext):
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{encargo}-{fieldname}.{ext}",
			"attached_to_doctype": "Encargo",
			"attached_to_name": encargo,
			"attached_to_field": fieldname,
			"is_private": 1,
			"content": content,
		}
	)
	file_doc.insert(ignore_permissions=True)
	return file_doc.file_url


@frappe.whitelist(methods=["POST"])
def confirm_purchase(
	encargo,
	barcode=None,
	price=None,
	product_image=None,
	label_image=None,
	supplier=None,
	proposed_supplier_name=None,
	qty=1,
	request_id=None,
):
	"""One purchase event per confirmation (Spec 020 §7); the rest of the demand stays visible."""
	_require_shopper()
	user = frappe.session.user
	barcode = (barcode or "").strip()[:140]
	qty = clean_qty(qty)
	request_id = clean_request_id(request_id)
	product = decode_image(product_image)
	label = decode_image(label_image)
	missing = missing_evidence(barcode, product, label, price)
	if missing:
		frappe.throw(_("Falta: {0}.").format(", ".join(missing)), title=_("Compra incompleta"))
	place_supplier, place_proposed = resolve_place(supplier, proposed_supplier_name)

	# Two shoppers buying the last units of the same Encargo serialize on this lock.
	row = demand.lock_encargo(encargo, ["name", "status", "requested_qty"])
	events = demand.locked_events(encargo) if row else []
	totals = demand.summarize(row.requested_qty, events, demand.locked_units(encargo)) if row else None
	decision, previous = purchase_decision(
		row, events, user, request_id, qty, totals.pending_supply_qty if totals else 0
	)
	if decision == "already_done":
		return purchase_result(
			encargo, previous.barcode_exception_status, previous.name, totals.pending_supply_qty
		)

	event = demand.add_event(
		encargo,
		demand.SHOPPER,
		demand.COMMITTED,
		qty,
		user,
		request_id=request_id,
		shopper_user=user,
		purchased_on=now_datetime(),
		supplier=place_supplier,
		proposed_supplier_name=place_proposed,
		purchase_barcode=barcode,
		purchase_price=flt(price, 2),
		purchase_currency=inventory.PURCHASE_CURRENCY,
		purchase_product_image=_save_evidence(encargo, "purchase_product_image", *product),
		purchase_label_image=_save_evidence(encargo, "purchase_label_image", *label),
	)
	status = barcode_exception.on_purchase(encargo, event, barcode)
	totals = demand.reconcile_encargo_supply(encargo)
	return purchase_result(encargo, status, event, totals.pending_supply_qty)


def purchase_result(encargo, barcode_status, supply_event=None, pending_supply_qty=0):
	"""Only the barcode outcome reaches the shopper; who resolves it stays hidden (Spec 017 §11)."""
	pending = barcode_status == barcode_exception.PENDING_APPROVAL
	return {
		"encargo": encargo,
		"supply_event": supply_event,
		"purchase_status": "PURCHASED",
		"pending_supply_qty": flt(pending_supply_qty),
		"pending_approval": int(pending),
		"message": _(barcode_exception.SHOPPER_MESSAGE) if pending else None,
	}


@frappe.whitelist(methods=["POST"])
def mark_not_found(encargo, supplier=None, proposed_supplier_name=None, notes=None):
	"""Log the attempt; the Encargo stays pending and visible. Review flag from the third."""
	_require_shopper()
	place_supplier, place_proposed = resolve_place(supplier, proposed_supplier_name)
	row = _lock_pending(encargo)
	if row.status != "Open" or flt(row.pending_supply_qty) <= 0:
		frappe.throw(_("Este Encargo ya no está disponible para compra."))

	count = cint(row.not_found_count) + 1
	attempt = frappe.get_doc(
		{
			"doctype": "Encargo Purchase Attempt",
			"name": frappe.generate_hash(length=10),
			"parent": encargo,
			"parenttype": "Encargo",
			"parentfield": "purchase_attempts",
			"idx": frappe.db.count("Encargo Purchase Attempt", {"parent": encargo}) + 1,
			"result": "NOT_FOUND",
			"attempted_on": now_datetime(),
			"shopper_user": frappe.session.user,
			"supplier": place_supplier,
			"proposed_supplier_name": place_proposed,
			"notes": (notes or "").strip()[:1000] or None,
		}
	)
	attempt.db_insert()
	values = {"not_found_count": count}
	if needs_review(count):
		values["needs_commercial_review"] = 1
	frappe.db.set_value("Encargo", encargo, values, update_modified=True)
	return {"encargo": encargo, "not_found_count": count, "needs_commercial_review": int(needs_review(count))}
