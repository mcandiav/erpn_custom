import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.file_manager import save_file

from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM
from erpn_custom.encargo.brand_supplier import optional_supplier_for_brand, require_brand
from erpn_custom.encargo.doctype.encargo.encargo import require_leaf_group
from erpn_custom.encargo.sales_order_line import sync_sales_order_line
from erpn_custom.selling.sales_person_assignment import resolve_sales_person_for_user


@frappe.whitelist()
def create_unknown_encargo(
	sales_order,
	description,
	brand,
	supplier=None,
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
	item_group=None,
	custom_departamento=None,
	attributes=None,
):
	"""Create Draft Encargo + ENCARGO-PENDIENTE row on a Draft Sales Order."""
	attributes = frappe.parse_json(attributes) if attributes else {}
	allowed = set(ATTRIBUTE_FIELDS.values())
	attributes = {fieldname: value for fieldname, value in attributes.items() if fieldname in allowed and value}
	so = frappe.get_doc("Sales Order", sales_order)
	if so.docstatus != 0:
		frappe.throw(_("Sales Order must be in Draft to add Encargo"))
	if so.is_new() or not so.name:
		frappe.throw(_("Save the Sales Order before adding Encargo"))

	brand, supplier = optional_supplier_for_brand(brand, supplier)
	require_leaf_group(item_group)

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

	pending_values = {
		"item_code": ENCARGO_PENDIENTE_ITEM,
		"item_name": description[:140],
		"description": description,
		"qty": qty,
		"rate": flt(rate),
		"uom": frappe.get_cached_value("Item", ENCARGO_PENDIENTE_ITEM, "stock_uom") or "Unidad",
		"conversion_factor": 1,
		"custom_stock_committed_qty": 0,
		"custom_encargo_qty": qty,
	}
	row = _unlinked_pending_row(so)
	if row:
		row.update(pending_values)
	else:
		so.append("items", pending_values)
		row = so.items[-1]
	so.save()

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
			"item_group": item_group,
			"custom_departamento": custom_departamento,
			**attributes,
		}
	)
	enc.insert()
	if image_b64 and image_filename:
		_attach_image(enc.name, image_filename, image_b64)

	frappe.db.set_value(
		"Sales Order Item",
		row.name,
		{"custom_encargo": enc.name, "item_name": description[:140]},
		update_modified=False,
	)
	sync_sales_order_line(frappe.get_doc("Encargo", enc.name))
	so.reload()
	return {"encargo": enc.name, "sales_order_item": row.name}


@frappe.whitelist()
def attach_reference_image(encargo, filename, content_b64):
	if not frappe.db.exists("Encargo", encargo):
		frappe.throw(_("Encargo not found"))
	file_url = _attach_image(encargo, filename, content_b64)
	return file_url


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def suppliers_for_brand_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link query: Suppliers that list the given Brand (excludes shoppers without brands)."""
	brand = (filters or {}).get("brand")
	if not brand:
		return []
	return frappe.db.sql(
		"""
		select distinct s.name, s.supplier_name
		from `tabSupplier` s
		inner join `tabSupplier Brand` sb
			on sb.parent = s.name and sb.parenttype = 'Supplier'
		where sb.brand = %(brand)s
			and ifnull(s.disabled, 0) = 0
			and (s.name like %(txt)s or ifnull(s.supplier_name, '') like %(txt)s)
		order by s.name
		limit %(start)s, %(page_len)s
		""",
		{
			"brand": brand,
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)


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


def _unlinked_pending_row(so):
	for item in so.items or []:
		if item.item_code == ENCARGO_PENDIENTE_ITEM and not item.get("custom_encargo"):
			return item
	return None


def _ensure_pending_item():
	if frappe.db.exists("Item", ENCARGO_PENDIENTE_ITEM):
		return
	from erpn_custom.patches.v0_0_13_encargo_foundation import ensure_encargo_pendiente_item

	ensure_encargo_pendiente_item()
