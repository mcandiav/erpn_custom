import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.file_manager import save_file

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM
from erpn_custom.selling.sales_person_assignment import resolve_sales_person_for_user


@frappe.whitelist()
def create_unknown_encargo(
	sales_order,
	description,
	brand,
	supplier,
	qty=1,
	rate=0,
	model=None,
	size=None,
	color=None,
	reference_url=None,
	notes=None,
	image_filename=None,
	image_b64=None,
	reference_image=None,
):
	"""Create Draft Encargo + ENCARGO-PENDIENTE row on a Draft Sales Order."""
	so = frappe.get_doc("Sales Order", sales_order)
	if so.docstatus != 0:
		frappe.throw(_("Sales Order must be in Draft to add Encargo"))
	if so.is_new() or not so.name:
		frappe.throw(_("Save the Sales Order before adding Encargo"))

	brand, supplier = _require_brand_supplier(brand, supplier)

	_ensure_pending_item()
	qty = flt(qty)
	if qty <= 0:
		frappe.throw(_("Qty must be greater than 0"))
	description = (description or "").strip()
	if not description:
		frappe.throw(_("Description is required"))

	sales_person = None
	resolved = resolve_sales_person_for_user(frappe.session.user)
	if resolved:
		sales_person = resolved["sales_person"]
	elif so.get("sales_team"):
		sales_person = so.sales_team[0].sales_person

	so.append(
		"items",
		{
			"item_code": ENCARGO_PENDIENTE_ITEM,
			"item_name": description[:140],
			"description": description,
			"qty": qty,
			"rate": flt(rate),
			"uom": frappe.get_cached_value("Item", ENCARGO_PENDIENTE_ITEM, "stock_uom") or "Nos",
			"conversion_factor": 1,
			"custom_stock_committed_qty": 0,
			"custom_encargo_qty": qty,
		},
	)
	so.save()
	row = so.items[-1]

	enc = frappe.get_doc(
		{
			"doctype": "Encargo",
			"naming_series": "ENC-.YYYY.-.#####",
			"status": "Draft",
			"source_type": "UNKNOWN_ITEM",
			"sales_order": so.name,
			"sales_order_item": row.name,
			"customer": so.customer,
			"sales_person": sales_person,
			"description": description,
			"brand": brand,
			"supplier": supplier,
			"model": model,
			"size": size,
			"color": color,
			"reference_url": reference_url,
			"notes": notes,
			"requested_qty": qty,
			"sale_rate": flt(rate),
			"purchase_status": "PENDING",
			"reception_status": "PENDING",
			"reference_image": reference_image,
		}
	)
	enc.insert()
	if image_b64 and image_filename:
		_attach_image(enc.name, image_filename, image_b64)

	frappe.db.set_value("Sales Order Item", row.name, "custom_encargo", enc.name, update_modified=False)
	so.reload()
	return {"encargo": enc.name, "sales_order_item": row.name}


@frappe.whitelist()
def attach_reference_image(encargo, filename, content_b64):
	if not frappe.db.exists("Encargo", encargo):
		frappe.throw(_("Encargo not found"))
	file_url = _attach_image(encargo, filename, content_b64)
	return file_url


def _require_brand_supplier(brand, supplier):
	brand = (brand or "").strip()
	supplier = (supplier or "").strip()
	if not brand or not supplier:
		frappe.throw(_("Brand and Supplier are required"))
	if not frappe.db.exists("Brand", brand):
		frappe.throw(_("Brand {0} not found").format(brand))
	if not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Supplier {0} not found").format(supplier))
	return brand, supplier


def _attach_image(encargo, filename, content_b64):
	import base64

	content = base64.b64decode(content_b64)
	file_doc = save_file(
		filename,
		content,
		"Encargo",
		encargo,
		folder=None,
		is_private=1,
		df="reference_image",
	)
	frappe.db.set_value("Encargo", encargo, "reference_image", file_doc.file_url)
	return file_doc.file_url


def _ensure_pending_item():
	if frappe.db.exists("Item", ENCARGO_PENDIENTE_ITEM):
		return
	from erpn_custom.patches.v0_0_13_encargo_foundation import ensure_encargo_pendiente_item

	ensure_encargo_pendiente_item()
