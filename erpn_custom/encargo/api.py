import base64

import frappe
from frappe import _
from frappe.utils import flt

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM
from erpn_custom.selling.sales_person_assignment import resolve_sales_person_for_user


@frappe.whitelist()
def create_unknown_encargo(
	sales_order,
	description,
	qty=1,
	rate=0,
	brand=None,
	suggested_store=None,
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
			"suggested_store": suggested_store,
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
	frappe.db.set_value("Encargo", encargo, "reference_image", file_url)
	return file_url


def _attach_image(encargo, filename, content_b64):
	content = base64.b64decode(content_b64)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"attached_to_doctype": "Encargo",
			"attached_to_name": encargo,
			"attached_to_field": "reference_image",
			"is_private": 1,
			"content": content,
		}
	)
	file_doc.save(ignore_permissions=True)
	return file_doc.file_url


def _ensure_pending_item():
	if frappe.db.exists("Item", ENCARGO_PENDIENTE_ITEM):
		return
	from erpn_custom.patches.v0_0_13_encargo_foundation import ensure_encargo_pendiente_item

	ensure_encargo_pendiente_item()
