"""Spec 017: barcode bought vs Item expected (KNOWN_ITEM) and its commercial resolution.

Buying and satisfying the demand are separate decisions: the Shopper always completes the
purchase; the seller responsible for the Sales Order approves or rejects the equivalence.
Spec 020: the exception belongs to one purchase event, not to the whole Encargo.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from erpn_custom.encargo import demand, inventory

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

LOCK_FIELDS = ["name", "status", "source_type", "sales_order", "expected_item"]
ENCARGO_LIST_FIELDS = ["name", "status", "sales_order", "customer", "description", "expected_item", "requested_qty"]
EVENT_LIST_FIELDS = [
	"name",
	"parent",
	"qty",
	"status",
	"purchase_barcode",
	"expected_barcode",
	"purchase_price",
	"purchase_currency",
	"supplier",
	"proposed_supplier_name",
	"purchase_product_image",
	"purchase_label_image",
	"purchased_on",
	"shopper_user",
	"barcode_exception_status",
	"barcode_resolved_on",
	"barcode_resolved_by",
	"barcode_resolution_comment",
]
SEARCH_FIELDS = ("name", "sales_order", "customer", "expected_item", "purchase_barcode", "description")


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
	return action == "reject" or mode == "override"


def pick_pending_event(events, supply_event=None):
	"""The purchase event to resolve: the one named, else the only one pending (Spec 020 §13)."""
	pending = [
		e
		for e in events
		if e.get("barcode_exception_status") == PENDING_APPROVAL and e.get("status") in demand.ACTIVE
	]
	if supply_event:
		return next((e for e in pending if e.get("name") == supply_event), None)
	return pending[0] if len(pending) == 1 else None


def matches_search(row, text):
	text = (text or "").strip().lower()
	return not text or any(text in str(row.get(field) or "").lower() for field in SEARCH_FIELDS)


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


def open_exception(encargo, supply_event):
	"""PENDING_APPROVAL on the purchase event plus the ToDo of the responsible seller; idempotent."""
	row = frappe.db.get_value("Encargo", encargo, ["sales_order", "expected_item"], as_dict=True)
	event = frappe.db.get_value(
		demand.EVENT, supply_event, ["purchase_barcode", "expected_barcode"], as_dict=True
	)
	values = {"barcode_exception_status": PENDING_APPROVAL}
	if not event.expected_barcode:
		values["expected_barcode"] = expected_barcode_text(row.expected_item) or None
	frappe.db.set_value(demand.EVENT, supply_event, values, update_modified=False)
	_tier, users = responsible_for_order(row.sales_order)
	_open_todos(
		encargo,
		TODO_EXCEPTION,
		users,
		_("aprobar o rechazar el código {0} comprado para el Item {1}.").format(event.purchase_barcode, row.expected_item),
	)


def on_purchase(encargo, supply_event, barcode):
	"""Runs in the confirm_purchase transaction; returns the barcode_exception_status of the event."""
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
		demand.EVENT,
		supply_event,
		{"barcode_exception_status": status, "expected_barcode": expected or None},
		update_modified=False,
	)
	if status == PENDING_APPROVAL:
		open_exception(encargo, supply_event)
	return status


def _require_view():
	if not set(VIEW_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def _lock_pending(encargo, supply_event):
	"""(Encargo, event, all events) under lock; the event must still wait for a decision."""
	row = frappe.db.get_value("Encargo", encargo, LOCK_FIELDS, as_dict=True, for_update=True)
	if not row or row.status != "Open":
		frappe.throw(_("El Encargo no tiene una excepción de barcode pendiente."))
	events = demand.locked_events(encargo)
	event = pick_pending_event(events, supply_event)
	if not event:
		frappe.throw(_("El Encargo no tiene una excepción de barcode pendiente."))
	return row, event, events


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


def _resolve(row, event, status, comment, mode):
	user = frappe.session.user
	values = {
		"barcode_exception_status": status,
		"barcode_resolved_on": now_datetime(),
		"barcode_resolved_by": user,
		"barcode_resolution_comment": comment or None,
	}
	if status == REJECTED:
		# The purchase stays in the history but stops consuming demand (Spec 020 §13).
		values["status"] = demand.REJECTED
	frappe.db.set_value(demand.EVENT, event.name, values, update_modified=False)
	text = _("Excepción barcode {0} ({1} u.): {2} por {3}.").format(event.purchase_barcode, event.qty, status, user)
	if mode == "override":
		text += " " + _("Override System Manager.")
	if comment:
		text += " " + comment
	_audit(row.name, text)


def _close_if_none_pending(encargo, events, resolved):
	if not any(e.name != resolved and e.get("barcode_exception_status") == PENDING_APPROVAL for e in events):
		close_todos(encargo, TODO_EXCEPTION)


@frappe.whitelist(methods=["POST"])
def approve(encargo, comment=None, supply_event=None):
	"""The code becomes the expected Item's; units of that purchase waiting in reception continue."""
	from erpn_custom.encargo import reception

	_require_view()
	row, event, events = _lock_pending(encargo, supply_event)
	mode, comment = _authorize(row, "approve", comment)
	owners = inventory.items_for_barcode(event.purchase_barcode)
	conflict = approval_conflict(row.expected_item, owners)
	if conflict:
		frappe.throw(
			_(
				"El código {0} pertenece al Item {1}. Rechaza la equivalencia o pide a System Manager corregir el maestro de Item."
			).format(event.purchase_barcode, conflict)
		)
	if not owners:
		inventory.add_barcode(row.expected_item, event.purchase_barcode)
	_resolve(row, event, APPROVED, comment, mode)
	_close_if_none_pending(encargo, events, event.name)
	units = reception.resume_after_barcode_decision(encargo, True, event.name)
	return {"encargo": encargo, "supply_event": event.name, "barcode_exception_status": APPROVED, "units": units}


@frappe.whitelist(methods=["POST"])
def reject(encargo, comment=None, supply_event=None):
	"""The purchase is kept but frees its quota: the demand goes back to the Shopper queue."""
	from erpn_custom.encargo import reception

	_require_view()
	row, event, events = _lock_pending(encargo, supply_event)
	mode, comment = _authorize(row, "reject", comment)
	_resolve(row, event, REJECTED, comment, mode)
	_close_if_none_pending(encargo, events, event.name)
	units = reception.resume_after_barcode_decision(encargo, False, event.name)
	totals = demand.reconcile_encargo_supply(encargo)
	_tier, users = responsible_for_order(row.sales_order)
	_open_todos(
		encargo,
		TODO_REJECTED,
		users,
		_("la compra rechazada volvió {0} u. a la cola Shopper; anula o modifica la OV {1} si el cliente ya no la quiere.").format(
			event.qty, row.sales_order
		),
	)
	return {
		"encargo": encargo,
		"supply_event": event.name,
		"barcode_exception_status": REJECTED,
		"pending_supply_qty": totals.pending_supply_qty if totals else None,
		"units": units,
	}


@frappe.whitelist()
def list_exceptions(view="pending", search=None, limit=200):
	"""Excepciones barcode: one row per purchase event (Spec 017 §12.3, Spec 020 §13)."""
	_require_view()
	if view not in VIEWS:
		frappe.throw(_("Vista desconocida."))
	limit = min(int(limit or 200), 500)
	events = frappe.get_all(
		demand.EVENT,
		filters={"parenttype": "Encargo", "barcode_exception_status": VIEWS[view]},
		fields=EVENT_LIST_FIELDS,
		order_by="purchased_on asc",
		limit_page_length=2000,
	)
	encargos = {}
	if events:
		for enc in frappe.get_all(
			"Encargo",
			filters={"name": ("in", list({e.parent for e in events})), "status": "Open"},
			fields=ENCARGO_LIST_FIELDS,
		):
			encargos[enc.name] = enc
	user, roles = frappe.session.user, frappe.get_roles()
	by_order = {}
	rows = []
	for event in events:
		enc = encargos.get(event.parent)
		if not enc:
			continue
		row = frappe._dict(
			{
				**enc,
				**{k: v for k, v in event.items() if k not in ("name", "parent", "status")},
				"supply_event": event.name,
				"supply_status": event.status,
				"purchase_supplier": event.supplier,
			}
		)
		if not matches_search(row, search):
			continue
		if row.sales_order not in by_order:
			by_order[row.sales_order] = responsible_for_order(row.sales_order)
		tier, users = by_order[row.sales_order]
		mode = resolution_mode(user, roles, users)
		row.update(
			{
				"responsible": users,
				"escalated": tier == ESCALATED,
				"can_resolve": bool(mode) and view == "pending",
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
		rows.append(row)
		if len(rows) >= limit:
			break
	return {"rows": rows}


