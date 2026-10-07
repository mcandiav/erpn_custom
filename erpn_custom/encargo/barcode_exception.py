"""Spec 017: barcode bought vs Item expected (KNOWN_ITEM) and its commercial resolution.

Buying and satisfying the demand are separate decisions: the Shopper always completes the
purchase; the seller responsible for the Sales Order approves or rejects the equivalence.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from erpn_custom.encargo import inventory

NOT_APPLICABLE = "NOT_APPLICABLE"
MATCH = "MATCH"
PENDING_APPROVAL = "PENDING_APPROVAL"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
REJECTED_LABEL = "Compra rechazada - decide el vendedor"
ESCALATED_LABEL = "Sin vendedor resoluble - escalado a System Manager"
SHOPPER_MESSAGE = "Compra registrada. El código difiere del esperado y quedó pendiente de aprobación comercial."
COMMERCIAL_ROLE = "ComercialFRA"
ADMIN_ROLE = "System Manager"
VIEW_ROLES = (COMMERCIAL_ROLE, ADMIN_ROLE)
COMMENT_MAX = 1000
TODO_EXCEPTION = "[Excepción barcode]"
TODO_REJECTED = "[Compra rechazada]"
VIEWS = {"pending": PENDING_APPROVAL, "rejected": REJECTED}
SELLER, OWNER, ESCALATED = "sales_person", "owner", "system_manager"

LOCK_FIELDS = [
	"name",
	"status",
	"source_type",
	"sales_order",
	"expected_item",
	"purchase_status",
	"purchase_barcode",
	"barcode_exception_status",
	"expected_barcode",
	"shopper_user",
	"purchased_on",
	"purchase_price",
	"purchase_currency",
	"purchase_supplier",
	"proposed_supplier_name",
	"purchase_product_image",
	"purchase_label_image",
	"barcode_resolved_on",
	"barcode_resolved_by",
	"barcode_resolution_comment",
]
LIST_FIELDS = [
	"name",
	"sales_order",
	"customer",
	"description",
	"expected_item",
	"expected_barcode",
	"purchase_barcode",
	"purchase_price",
	"purchase_currency",
	"purchase_supplier",
	"proposed_supplier_name",
	"purchase_product_image",
	"purchase_label_image",
	"purchased_on",
	"shopper_user",
	"requested_qty",
	"barcode_exception_status",
	"barcode_resolved_on",
	"barcode_resolved_by",
	"barcode_resolution_comment",
]
# The cleared purchase goes to the attempts history first (Spec 017 §8.4 B).
CLEARED_PURCHASE = {
	"purchase_status": "PENDING",
	"shopper_user": None,
	"purchased_on": None,
	"purchase_barcode": None,
	"purchase_price": 0,
	"purchase_supplier": None,
	"proposed_supplier_name": None,
	"purchase_product_image": None,
	"purchase_label_image": None,
	"barcode_exception_status": "",
	"expected_barcode": None,
	"barcode_resolved_on": None,
	"barcode_resolved_by": None,
	"barcode_resolution_comment": None,
}


def purchase_outcome(source_type, expected_item, barcode_items, expected_has_barcodes):
	"""(barcode_exception_status, adopt_code) for a confirmed purchase (Spec 017 §7, §9)."""
	if source_type != "KNOWN_ITEM" or not expected_item:
		return "", False
	barcode_item = expected_item if expected_item in barcode_items else (barcode_items[0] if barcode_items else None)
	decision = inventory.known_item_decision(expected_item, barcode_item, expected_has_barcodes)
	if decision == "use":
		return MATCH, False
	if decision == "adopt":
		return MATCH, True
	return PENDING_APPROVAL, False


def approval_conflict(expected_item, barcode_items):
	"""The other Item already carrying the code: approval stays blocked (Spec 017 §8.3)."""
	others = [item for item in barcode_items if item != expected_item]
	return others[0] if others else None


def responsible(tiers):
	"""(tier, users): the first tier with a valid user (Spec 017 §8.1.1)."""
	for tier, users in tiers:
		if users:
			return tier, list(users)
	return None, []


def resolution_mode(user, roles, responsible_users):
	if user in responsible_users:
		return "responsible"
	if ADMIN_ROLE in roles:
		return "override"
	return None


def comment_required(action, mode):
	"""Spec 017 §16: optional only for a normal approval."""
	return action in ("reject", "new_purchase") or mode == "override"


def clean_comment(value):
	return (value or "").strip()[:COMMENT_MAX]


def status_label(status):
	return {
		MATCH: _("Barcode coincide"),
		PENDING_APPROVAL: _("Excepción barcode - pendiente aprobación"),
		APPROVED: _("Barcode aprobado"),
		REJECTED: _(REJECTED_LABEL),
	}.get(status, "")


def expected_barcode_text(item_code):
	if not item_code:
		return ""
	codes = frappe.get_all(
		"Item Barcode", filters={"parent": item_code, "parenttype": "Item"}, pluck="barcode", order_by="idx asc"
	)
	return ", ".join(codes)


def _active(users):
	return [
		user
		for user in users
		if user and user != "Guest" and frappe.db.get_value("User", user, "enabled")
	]


def _with_role(users, role):
	return [user for user in users if user and role in frappe.get_roles(user)]


def _system_managers():
	users = frappe.get_all("Has Role", filters={"role": ADMIN_ROLE, "parenttype": "User"}, pluck="parent")
	active = [user for user in _active(sorted(set(users))) if user != "Administrator"]
	return active or ["Administrator"]


def responsible_for_order(sales_order):
	"""Sales Team seller with ComercialFRA, else the order owner with ComercialFRA, else System Manager."""
	sellers = []
	if sales_order:
		for sales_person in frappe.get_all(
			"Sales Team", filters={"parent": sales_order, "parenttype": "Sales Order"}, pluck="sales_person"
		):
			employee = frappe.db.get_value("Sales Person", sales_person, "employee")
			user = employee and frappe.db.get_value("Employee", employee, "user_id")
			if user and user not in sellers:
				sellers.append(user)
	owner = frappe.db.get_value("Sales Order", sales_order, "owner") if sales_order else None
	return responsible(
		[
			(SELLER, _active(_with_role(sellers, COMMERCIAL_ROLE))),
			(OWNER, _active(_with_role([owner], COMMERCIAL_ROLE))),
			(ESCALATED, _system_managers()),
		]
	)


def _open_todos(encargo, marker, users, text):
	"""One open ToDo per user and kind: refreshes and retries never duplicate it."""
	for user in users:
		if frappe.db.exists(
			"ToDo",
			{
				"reference_type": "Encargo",
				"reference_name": encargo,
				"allocated_to": user,
				"status": "Open",
				"description": ("like", f"{marker}%"),
			},
		):
			continue
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": user,
				"reference_type": "Encargo",
				"reference_name": encargo,
				"priority": "High",
				"description": f"{marker} {encargo}: {text}",
			}
		).insert(ignore_permissions=True)


def close_todos(encargo, marker):
	for name in frappe.get_all(
		"ToDo",
		filters={
			"reference_type": "Encargo",
			"reference_name": encargo,
			"status": "Open",
			"description": ("like", f"{marker}%"),
		},
		pluck="name",
	):
		todo = frappe.get_doc("ToDo", name)
		todo.status = "Closed"
		todo.save(ignore_permissions=True)


def _audit(encargo, text):
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Encargo",
			"reference_name": encargo,
			"content": text,
		}
	).insert(ignore_permissions=True)


def open_exception(encargo):
	"""PENDING_APPROVAL plus the ToDo of the responsible seller; idempotent."""
	row = frappe.db.get_value(
		"Encargo", encargo, ["sales_order", "expected_item", "purchase_barcode", "expected_barcode"], as_dict=True
	)
	values = {"barcode_exception_status": PENDING_APPROVAL}
	if not row.expected_barcode:
		values["expected_barcode"] = expected_barcode_text(row.expected_item) or None
	frappe.db.set_value("Encargo", encargo, values, update_modified=True)
	_tier, users = responsible_for_order(row.sales_order)
	_open_todos(
		encargo,
		TODO_EXCEPTION,
		users,
		_("aprobar o rechazar el código {0} comprado para el Item {1}.").format(row.purchase_barcode, row.expected_item),
	)


def on_purchase(encargo, barcode):
	"""Runs in the confirm_purchase transaction; returns the barcode_exception_status written."""
	row = frappe.db.get_value("Encargo", encargo, ["source_type", "expected_item"], as_dict=True)
	if not row or row.source_type != "KNOWN_ITEM" or not row.expected_item:
		return ""
	expected = expected_barcode_text(row.expected_item)
	status, adopt = purchase_outcome(
		row.source_type, row.expected_item, inventory.items_for_barcode(barcode), bool(expected)
	)
	if adopt:
		inventory.add_barcode(row.expected_item, barcode)
		expected = barcode
	frappe.db.set_value(
		"Encargo",
		encargo,
		{"barcode_exception_status": status, "expected_barcode": expected or None},
		update_modified=False,
	)
	if status == PENDING_APPROVAL:
		open_exception(encargo)
	return status


def _require_view():
	if not set(VIEW_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def _lock(encargo):
	return frappe.db.get_value("Encargo", encargo, LOCK_FIELDS, as_dict=True, for_update=True)


def _require_state(row, status):
	if (
		not row
		or row.status != "Open"
		or row.purchase_status != "PURCHASED"
		or row.barcode_exception_status != status
	):
		if status == PENDING_APPROVAL:
			frappe.throw(_("El Encargo no tiene una excepción de barcode pendiente."))
		frappe.throw(_("El Encargo no tiene una compra rechazada esperando decisión."))


def _authorize(row, action, comment):
	_tier, users = responsible_for_order(row.sales_order)
	mode = resolution_mode(frappe.session.user, frappe.get_roles(), users)
	if not mode:
		frappe.throw(
			_("Solo el vendedor responsable de la OV ({0}) o System Manager pueden resolver.").format(", ".join(users)),
			frappe.PermissionError,
		)
	comment = clean_comment(comment)
	if comment_required(action, mode) and not comment:
		frappe.throw(_("Indica el motivo."))
	return mode, comment


def _resolve(row, status, comment, mode):
	user = frappe.session.user
	frappe.db.set_value(
		"Encargo",
		row.name,
		{
			"barcode_exception_status": status,
			"barcode_resolved_on": now_datetime(),
			"barcode_resolved_by": user,
			"barcode_resolution_comment": comment or None,
		},
		update_modified=True,
	)
	text = _("Excepción barcode {0}: {1} por {2}.").format(row.purchase_barcode, status, user)
	if mode == "override":
		text += " " + _("Override System Manager.")
	if comment:
		text += " " + comment
	_audit(row.name, text)


@frappe.whitelist(methods=["POST"])
def approve(encargo, comment=None):
	"""The code becomes the expected Item's; units waiting in reception continue (Spec 017 §8.2)."""
	from erpn_custom.encargo import reception

	_require_view()
	row = _lock(encargo)
	_require_state(row, PENDING_APPROVAL)
	mode, comment = _authorize(row, "approve", comment)
	owners = inventory.items_for_barcode(row.purchase_barcode)
	conflict = approval_conflict(row.expected_item, owners)
	if conflict:
		frappe.throw(
			_(
				"El código {0} pertenece al Item {1}. Rechaza la equivalencia o pide a System Manager corregir el maestro de Item."
			).format(row.purchase_barcode, conflict)
		)
	if not owners:
		inventory.add_barcode(row.expected_item, row.purchase_barcode)
	_resolve(row, APPROVED, comment, mode)
	close_todos(encargo, TODO_EXCEPTION)
	units = reception.resume_after_barcode_decision(encargo, approved=True)
	return {"encargo": encargo, "barcode_exception_status": APPROVED, "units": units}


@frappe.whitelist(methods=["POST"])
def reject(encargo, comment=None):
	"""The purchase stays PURCHASED and stops satisfying the demand; the seller decides next (§8.4)."""
	from erpn_custom.encargo import reception

	_require_view()
	row = _lock(encargo)
	_require_state(row, PENDING_APPROVAL)
	mode, comment = _authorize(row, "reject", comment)
	_resolve(row, REJECTED, comment, mode)
	close_todos(encargo, TODO_EXCEPTION)
	_tier, users = responsible_for_order(row.sales_order)
	_open_todos(
		encargo,
		TODO_REJECTED,
		users,
		_("anular o modificar la OV {0}, o solicitar nueva compra.").format(row.sales_order),
	)
	units = reception.resume_after_barcode_decision(encargo, approved=False)
	return {"encargo": encargo, "barcode_exception_status": REJECTED, "units": units}


def _archive_rejected_purchase(row, comment):
	frappe.get_doc(
		{
			"doctype": "Encargo Purchase Attempt",
			"name": frappe.generate_hash(length=10),
			"parent": row.name,
			"parenttype": "Encargo",
			"parentfield": "purchase_attempts",
			"idx": frappe.db.count("Encargo Purchase Attempt", {"parent": row.name}) + 1,
			"result": "BARCODE_REJECTED",
			"attempted_on": row.purchased_on,
			"shopper_user": row.shopper_user,
			"supplier": row.purchase_supplier,
			"proposed_supplier_name": row.proposed_supplier_name,
			"notes": comment,
			"purchase_barcode": row.purchase_barcode,
			"expected_barcode": row.expected_barcode,
			"purchase_price": row.purchase_price,
			"purchase_currency": row.purchase_currency,
			"purchase_product_image": row.purchase_product_image,
			"purchase_label_image": row.purchase_label_image,
			"resolved_on": row.barcode_resolved_on,
			"resolved_by": row.barcode_resolved_by,
			"resolution_comment": row.barcode_resolution_comment,
		}
	).db_insert()


@frappe.whitelist(methods=["POST"])
def request_new_purchase(encargo, comment=None):
	"""Rejected purchase -> immutable history; the Encargo returns to the Shopper queue (§8.4 B)."""
	_require_view()
	row = _lock(encargo)
	_require_state(row, REJECTED)
	mode, comment = _authorize(row, "new_purchase", comment)
	_archive_rejected_purchase(row, comment)
	frappe.db.set_value("Encargo", encargo, CLEARED_PURCHASE, update_modified=True)
	close_todos(encargo, TODO_REJECTED)
	text = _("Solicitud de nueva compra por {0}.").format(frappe.session.user)
	if mode == "override":
		text += " " + _("Override System Manager.")
	_audit(encargo, f"{text} {comment}")
	return {"encargo": encargo, "purchase_status": "PENDING"}


@frappe.whitelist()
def list_exceptions(view="pending", search=None, limit=200):
	"""Excepciones barcode: Encargos, because the exception exists from the purchase (Spec 017 §12.3)."""
	_require_view()
	if view not in VIEWS:
		frappe.throw(_("Vista desconocida."))
	text = (search or "").strip()
	or_filters = None
	if text:
		like = f"%{text}%"
		or_filters = {
			"name": ("like", like),
			"sales_order": ("like", like),
			"customer": ("like", like),
			"expected_item": ("like", like),
			"purchase_barcode": ("like", like),
			"description": ("like", like),
		}
	rows = frappe.get_all(
		"Encargo",
		filters={"barcode_exception_status": VIEWS[view], "status": "Open"},
		or_filters=or_filters,
		fields=LIST_FIELDS,
		order_by="purchased_on asc",
		limit_page_length=min(int(limit or 200), 500),
	)
	user, roles = frappe.session.user, frappe.get_roles()
	by_order = {}
	for row in rows:
		if row.sales_order not in by_order:
			by_order[row.sales_order] = responsible_for_order(row.sales_order)
		tier, users = by_order[row.sales_order]
		mode = resolution_mode(user, roles, users)
		row.update(
			{
				"responsible": users,
				"escalated": tier == ESCALATED,
				"can_resolve": bool(mode),
				"override": mode == "override",
				"label": status_label(row.barcode_exception_status),
				"expected_item_name": frappe.get_cached_value("Item", row.expected_item, "item_name")
				if row.expected_item
				else None,
				"conflict_item": approval_conflict(row.expected_item, inventory.items_for_barcode(row.purchase_barcode))
				if row.barcode_exception_status == PENDING_APPROVAL
				else None,
			}
		)
	return {"rows": rows}
