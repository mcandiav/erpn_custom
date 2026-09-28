import base64
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

SHOPPER_ROLE = "ShopperFRA"
ALLOWED_ROLES = (SHOPPER_ROLE, "System Manager")
REVIEW_AFTER_NOT_FOUND = 3
ALL_PLACES = "TODOS"

# Never add customer, sales order, sale rate or seller: the shopper must not see them.
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
LOCK_FIELDS = ["name", "status", "purchase_status", "shopper_user", "purchase_barcode", "requested_qty", "not_found_count"]
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


def purchase_decision(row, user, barcode):
	"""'confirm' for a pending Encargo, 'already_done' for a retry of the same purchase."""
	if not row or row.get("status") != "Open":
		frappe.throw(_("Este Encargo ya no está disponible para compra."))
	if row.get("purchase_status") == "PURCHASED":
		if row.get("shopper_user") == user and row.get("purchase_barcode") == barcode:
			return "already_done"
		frappe.throw(_("Este Encargo ya fue comprado por otro shopper."))
	if row.get("purchase_status") != "PENDING":
		frappe.throw(_("Este Encargo ya no está disponible para compra."))
	return "confirm"


def require_full_qty(requested_qty, confirm_full_qty):
	if flt(requested_qty) > 1 and not cint(confirm_full_qty):
		frappe.throw(
			_("Este Encargo pide {0} unidades: confirma que compraste todas.").format(f"{flt(requested_qty):g}")
		)


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


def _image_url(encargo, file_url):
	if not file_url:
		return None
	if file_url.startswith("/private/"):
		return f"/api/method/erpn_custom.encargo.shopper.reference_image?encargo={encargo}"
	return file_url


def _variant(row):
	parts = [f"{label}: {row.get(field)}" for field, label in ATTRIBUTE_LABELS if row.get(field)]
	if not parts:
		parts = [value for value in (row.get("size"), row.get("color")) if value]
	return " · ".join(parts)


def _card(row):
	return {
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
		"reference_url": row.reference_url,
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
		filters={"status": "Open", "purchase_status": "PENDING"},
		fields=LIST_FIELDS,
		order_by="creation asc",
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
	return [_card(row) for row in rows]


@frappe.whitelist()
def reference_image(encargo):
	_require_shopper()
	row = frappe.db.get_value(
		"Encargo", encargo, ["status", "purchase_status", "reference_image"], as_dict=True
	)
	if not row or row.status != "Open" or row.purchase_status != "PENDING" or not row.reference_image:
		raise frappe.DoesNotExistError
	file_name = frappe.db.get_value("File", {"file_url": row.reference_image}, "name")
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
	confirm_full_qty=0,
):
	"""Evidence + PURCHASED in one request transaction; any error leaves the Encargo pending."""
	_require_shopper()
	user = frappe.session.user
	barcode = (barcode or "").strip()[:140]
	product = decode_image(product_image)
	label = decode_image(label_image)
	missing = missing_evidence(barcode, product, label, price)
	if missing:
		frappe.throw(_("Falta: {0}.").format(", ".join(missing)), title=_("Compra incompleta"))
	place_supplier, place_proposed = resolve_place(supplier, proposed_supplier_name)

	row = _lock_pending(encargo)
	if purchase_decision(row, user, barcode) == "already_done":
		return {"encargo": encargo, "purchase_status": "PURCHASED"}
	require_full_qty(row.requested_qty, confirm_full_qty)

	frappe.db.set_value(
		"Encargo",
		encargo,
		{
			"purchase_status": "PURCHASED",
			"shopper_user": user,
			"purchased_on": now_datetime(),
			"purchase_barcode": barcode,
			"purchase_price": flt(price, 2),
			"purchase_supplier": place_supplier,
			"proposed_supplier_name": place_proposed,
			"purchase_product_image": _save_evidence(encargo, "purchase_product_image", *product),
			"purchase_label_image": _save_evidence(encargo, "purchase_label_image", *label),
		},
		update_modified=True,
	)
	return {"encargo": encargo, "purchase_status": "PURCHASED"}


@frappe.whitelist(methods=["POST"])
def mark_not_found(encargo, supplier=None, proposed_supplier_name=None, notes=None):
	"""Log the attempt; the Encargo stays pending and visible. Review flag from the third."""
	_require_shopper()
	place_supplier, place_proposed = resolve_place(supplier, proposed_supplier_name)
	row = _lock_pending(encargo)
	if row.status != "Open" or row.purchase_status != "PENDING":
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
