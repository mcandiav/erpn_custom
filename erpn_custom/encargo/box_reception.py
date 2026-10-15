"""Spec 018 §23: provisional reception by physical BOX.

A read in a DRAFT box only stores a line. Pressing Finalizar queues a job that runs the existing
one-unit reception (reception.process_scan) per line, one commit per line; the line's scan_event_id
becomes the unit's scan_event_id, so a repeated close never creates a second unit.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime

from erpn_custom.encargo import inventory, materialization, reception

BOX = "Recepcion Caja"
LINE = "Recepcion Caja Linea"
UNIT = reception.UNIT

DRAFT = "DRAFT"
FINALIZING = "FINALIZING"
FINALIZED = "FINALIZED"
FINALIZED_WITH_EXCEPTIONS = "FINALIZED_WITH_EXCEPTIONS"
CANCELLED = "CANCELLED"
CLOSED = (FINALIZED, FINALIZED_WITH_EXCEPTIONS)

ACTIVE = "ACTIVE"
DISCARDED = "DISCARDED"
PROCESSED = "PROCESSED"
ERROR = "ERROR"

# Technical failures retried by the job before the box shows up in "Cajas con incidencias".
MAX_AUTO_ATTEMPTS = 3
# A FINALIZING box without progress for this long is resumed by the scheduler.
STALE_MINUTES = 10
JOB_TIMEOUT = 3600
EXTERNAL_REF_MAX = 140
PREVIEW_MAX = 240
ERROR_MAX = 1000
LIST_MAX = 200

BOX_FIELDS = [
	"name",
	"status",
	"external_ref",
	"notes",
	"opened_on",
	"opened_by",
	"active_lines",
	"discarded_lines",
	"processed_lines",
	"exception_lines",
	"error_lines",
	"finalize_requested_on",
	"finalize_requested_by",
	"finalized_on",
	"cancelled_on",
	"cancelled_by",
	"job_heartbeat",
	"last_error",
]
LINE_FIELDS = [
	"name",
	"box",
	"ordinal",
	"status",
	"scanned_code",
	"scan_event_id",
	"preview",
	"scanned_on",
	"scanned_by",
	"discarded_on",
	"discarded_by",
	"reception_unit",
	"processed_on",
	"attempts",
	"error_message",
]
UNIT_RESULT_FIELDS = ["name", "status", "destination", "encargo", "customer", "sales_order", "item", "item_name",
	"materialization_status", "message", "materialization_message", "stock_entry"]


# ---------------------------------------------------------------- rules


def can_read(roles):
	return reception.is_receptor(roles) or reception.is_commercial(roles)


def is_exception_unit(unit):
	"""A unit still waiting for a business decision (classification, barcode, cost, OV link)."""
	status = unit.get("status")
	if status == reception.RETURNED:
		return False
	if status != reception.POSTED:
		return True
	return unit.get("materialization_status") == materialization.ERROR


def pending_lines(lines):
	"""Lines the close job still has to process: never consumed, or a technical failure with attempts left."""
	return [
		line
		for line in lines
		if line.get("status") == ACTIVE
		or (line.get("status") == ERROR and cint(line.get("attempts")) < MAX_AUTO_ATTEMPTS)
	]


def line_totals(lines, units):
	totals = {"active_lines": 0, "discarded_lines": 0, "processed_lines": 0, "error_lines": 0}
	for line in lines:
		status = line.get("status")
		if status == DISCARDED:
			totals["discarded_lines"] += 1
			continue
		totals["active_lines"] += 1
		if status == PROCESSED:
			totals["processed_lines"] += 1
		elif status == ERROR:
			totals["error_lines"] += 1
	totals["exception_lines"] = sum(1 for unit in units if is_exception_unit(unit))
	return totals


def final_status(lines, units):
	"""None while a line is still unprocessed; otherwise FINALIZED or FINALIZED_WITH_EXCEPTIONS (§23.4)."""
	if any(line.get("status") in (ACTIVE, ERROR) for line in lines):
		return None
	return FINALIZED_WITH_EXCEPTIONS if any(is_exception_unit(unit) for unit in units) else FINALIZED


def is_stale(heartbeat, now, minutes=STALE_MINUTES):
	return not heartbeat or get_datetime(heartbeat) <= now - timedelta(minutes=minutes)


def repeats_previous(previous_code, code):
	"""Possible double read: same code as the previous active read. Only a warning, never blocks (§23.3)."""
	return bool(previous_code) and previous_code == code


def exact_codes(rows, codes):
	"""The database collation ignores case; QR links do not."""
	return {row for row in rows if row in codes}


def clean_external_ref(value):
	return (value or "").strip()[:EXTERNAL_REF_MAX]


# ---------------------------------------------------------------- helpers


def _require(allowed):
	if not allowed(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def _lock_box(box):
	head = frappe.db.get_value(BOX, box, BOX_FIELDS, as_dict=True, for_update=True)
	if not head:
		frappe.throw(_("Caja {0} no encontrada.").format(box))
	return head


def _require_draft(head):
	if head.status != DRAFT:
		frappe.throw(_("La caja {0} ya no está en borrador.").format(head.name))


def _lines(box, fields=None):
	return frappe.get_all(LINE, filters={"box": box}, fields=fields or LINE_FIELDS, order_by="ordinal asc")


def _box_units(box):
	return frappe.get_all(UNIT, filters={"box": box}, fields=UNIT_RESULT_FIELDS)


def _update_counts(box):
	lines = _lines(box, ["status", "attempts"])
	totals = line_totals(lines, _box_units(box))
	frappe.db.set_value(BOX, box, totals, update_modified=False)
	return totals


def preview_for(code):
	"""Read-only hint shown while scanning: no barcode, Item, exception, reservation or event is written (§23.8 #8)."""
	try:
		items = inventory.items_for_barcode(code)
		candidates = reception._candidates(code, items)
		if candidates:
			enc = frappe.db.get_value("Encargo", candidates[0].name, ["name", "customer", "sales_order"], as_dict=True)
			text = " · ".join(filter(None, [enc.name, enc.customer, enc.sales_order]))
		elif items:
			text = " · ".join(filter(None, [items[0], frappe.db.get_value("Item", items[0], "item_name")]))
		else:
			text = _("Sin coincidencia: se resolverá al finalizar")
	except Exception:
		text = ""
	return (text or "")[:PREVIEW_MAX]


def line_result(line, unit=None, duplicate=False, repeated=False):
	result = {key: line.get(key) for key in LINE_FIELDS}
	result.update({"duplicate": int(bool(duplicate)), "repeated": int(bool(repeated))})
	if unit:
		title, kind = reception.screen(
			unit.status, unit.destination, bool(unit.encargo), unit.materialization_status, unit.encargo
		)
		result["unit"] = {
			"name": unit.name,
			"screen": title,
			"kind": kind,
			"status": unit.status,
			"encargo": unit.encargo,
			"customer": unit.customer,
			"sales_order": unit.sales_order,
			"item": unit.item,
			"item_name": unit.item_name,
			"stock_entry": unit.stock_entry,
			"message": unit.message or unit.materialization_message,
			"exception": int(is_exception_unit(unit)),
		}
	return result


def box_detail(box):
	head = frappe.db.get_value(BOX, box, BOX_FIELDS, as_dict=True)
	if not head:
		frappe.throw(_("Caja {0} no encontrada.").format(box))
	units = {unit.name: unit for unit in _box_units(box)}
	head["lines"] = [line_result(line, units.get(line.reception_unit)) for line in _lines(box)]
	return head


# ---------------------------------------------------------------- draft endpoints


@frappe.whitelist(methods=["POST"])
def open_box(external_ref=None, notes=None):
	"""Abrir caja: the BOX number is generated; the carrier label is optional (§23.3)."""
	_require(reception.is_receptor)
	doc = frappe.get_doc(
		{
			"doctype": BOX,
			"status": DRAFT,
			"external_ref": clean_external_ref(external_ref),
			"notes": reception.clean_notes(notes),
			"opened_on": now_datetime(),
			"opened_by": frappe.session.user,
		}
	)
	doc.insert(ignore_permissions=True)
	return box_detail(doc.name)


@frappe.whitelist()
def get_box(box):
	_require(can_read)
	return box_detail(box)


@frappe.whitelist(methods=["POST"])
def add_line(box, code, scan_event_id):
	"""One read = one line of the draft. Nothing in inventory or demand changes until Finalizar (§23.4)."""
	_require(reception.is_receptor)
	code = reception.clean_code(code)
	if not code:
		frappe.throw(_("Escanea o escribe un código."))
	scan_event_id = reception.clean_scan_event_id(scan_event_id)
	existing = frappe.db.get_value(LINE, {"scan_event_id": scan_event_id}, LINE_FIELDS, as_dict=True)
	if existing:
		return line_result(existing, duplicate=True)
	head = _lock_box(box)
	_require_draft(head)
	last = frappe.get_all(LINE, filters={"box": box}, fields=["ordinal"], order_by="ordinal desc", limit_page_length=1)
	previous = frappe.get_all(
		LINE,
		filters={"box": box, "status": ACTIVE},
		fields=["scanned_code"],
		order_by="ordinal desc",
		limit_page_length=1,
	)
	line = frappe.get_doc(
		{
			"doctype": LINE,
			"box": box,
			"ordinal": (cint(last[0].ordinal) if last else 0) + 1,
			"status": ACTIVE,
			"scanned_code": code,
			"scan_event_id": scan_event_id,
			"preview": preview_for(code),
			"scanned_on": now_datetime(),
			"scanned_by": frappe.session.user,
		}
	)
	try:
		line.insert(ignore_permissions=True)
	except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
		# The same read arrived twice at once: the first one wins.
		frappe.db.rollback()
		return line_result(frappe.db.get_value(LINE, {"scan_event_id": scan_event_id}, LINE_FIELDS, as_dict=True), duplicate=True)
	_update_counts(box)
	return line_result(line.as_dict(), repeated=repeats_previous(previous[0].scanned_code if previous else None, code))


@frappe.whitelist(methods=["POST"])
def discard_line(box, line):
	"""Quitar lectura: only in DRAFT, no reason asked, the line stays as an audited discard (§23.3)."""
	_require(reception.is_receptor)
	head = _lock_box(box)
	_require_draft(head)
	row = frappe.db.get_value(LINE, line, LINE_FIELDS, as_dict=True, for_update=True)
	if not row or row.box != box:
		frappe.throw(_("La lectura no pertenece a la caja {0}.").format(box))
	if row.status == DISCARDED:
		return line_result(row)
	if row.status != ACTIVE:
		frappe.throw(_("Solo se quitan lecturas activas."))
	values = {"status": DISCARDED, "discarded_on": now_datetime(), "discarded_by": frappe.session.user}
	frappe.db.set_value(LINE, line, values, update_modified=False)
	row.update(values)
	_update_counts(box)
	return line_result(row)


@frappe.whitelist(methods=["POST"])
def cancel_box(box):
	"""Anular caja borrador: allowed with zero reads; no stock or Encargo effect; never reopened (§23.8 #1)."""
	_require(reception.is_receptor)
	head = _lock_box(box)
	if head.status == CANCELLED:
		return box_detail(box)
	_require_draft(head)
	frappe.db.set_value(
		BOX,
		box,
		{"status": CANCELLED, "cancelled_on": now_datetime(), "cancelled_by": frappe.session.user},
		update_modified=True,
	)
	return box_detail(box)


@frappe.whitelist(methods=["POST"])
def finalize_box(box):
	"""Finalizar recepción: physical confirmation; the units are processed by a queued job (§23.8 #3)."""
	_require(reception.is_receptor)
	head = _lock_box(box)
	if head.status in (FINALIZING, *CLOSED):
		return box_detail(box)
	_require_draft(head)
	if not frappe.db.count(LINE, {"box": box, "status": ACTIVE}):
		frappe.throw(_("Una caja sin lecturas activas no puede finalizarse. Puedes anularla."))
	now = now_datetime()
	frappe.db.set_value(
		BOX,
		box,
		{
			"status": FINALIZING,
			"finalize_requested_on": now,
			"finalize_requested_by": frappe.session.user,
			"job_heartbeat": now,
		},
		update_modified=True,
	)
	enqueue_close(box, after_commit=True)
	return box_detail(box)


# ---------------------------------------------------------------- close job


def enqueue_close(box, after_commit=False):
	frappe.enqueue(
		"erpn_custom.encargo.box_reception.run_box_close",
		queue="long",
		timeout=JOB_TIMEOUT,
		job_id=f"erpn_custom:box_close:{box}",
		deduplicate=True,
		enqueue_after_commit=after_commit,
		box=box,
	)


def run_box_close(box):
	if frappe.db.get_value(BOX, box, "status") != FINALIZING:
		return
	for line in pending_lines(_lines(box, ["name", "status", "attempts"])):
		process_line(line.name)
	finish_box(box)


def process_line(name):
	"""One line, one transaction: a failure rolls back only this unit and leaves the line retryable."""
	box = None
	try:
		row = frappe.db.get_value(LINE, name, LINE_FIELDS, as_dict=True, for_update=True)
		if not row or row.status not in (ACTIVE, ERROR):
			frappe.db.commit()
			return
		box = row.box
		if frappe.db.get_value(BOX, box, "status") != FINALIZING:
			frappe.db.commit()
			return
		result = reception.process_scan(
			row.scanned_code, row.scan_event_id, row.scanned_by, row.scanned_on, box=box, box_line=row.name
		)
		now = now_datetime()
		frappe.db.set_value(
			LINE,
			name,
			{"status": PROCESSED, "reception_unit": result["unit"], "processed_on": now, "error_message": None},
			update_modified=False,
		)
		frappe.db.set_value(BOX, box, "job_heartbeat", now, update_modified=False)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.clear_messages()
		message = frappe.get_traceback()[-ERROR_MAX:]
		row = frappe.db.get_value(LINE, name, ["box", "attempts"], as_dict=True) or {}
		box = box or row.get("box")
		frappe.db.set_value(
			LINE,
			name,
			{"status": ERROR, "attempts": cint(row.get("attempts")) + 1, "error_message": message},
			update_modified=False,
		)
		if box:
			frappe.db.set_value(BOX, box, {"job_heartbeat": now_datetime(), "last_error": message}, update_modified=False)
		frappe.db.commit()


def finish_box(box):
	head = _lock_box(box)
	if head.status != FINALIZING:
		frappe.db.commit()
		return head.status
	lines = _lines(box, ["status", "attempts"])
	units = _box_units(box)
	values = line_totals(lines, units)
	status = final_status(lines, units)
	if status:
		values.update({"status": status, "finalized_on": now_datetime(), "last_error": None})
	frappe.db.set_value(BOX, box, values, update_modified=bool(status))
	frappe.db.commit()
	return status or FINALIZING


def refresh_finished_box(box):
	"""Called inside the unit's own transaction after an exception is resolved; never commits."""
	status = frappe.db.get_value(BOX, box, "status")
	if status not in CLOSED:
		return
	units = _box_units(box)
	values = {"exception_lines": sum(1 for unit in units if is_exception_unit(unit))}
	values["status"] = FINALIZED_WITH_EXCEPTIONS if values["exception_lines"] else FINALIZED
	frappe.db.set_value(BOX, box, values, update_modified=values["status"] != status)


def tick_from_scheduler():
	"""Resumes FINALIZING boxes whose job died or never started; finishes boxes already fully processed."""
	now = now_datetime()
	for row in frappe.get_all(BOX, filters={"status": FINALIZING}, fields=["name", "job_heartbeat"]):
		if not is_stale(row.job_heartbeat, now):
			continue
		if pending_lines(_lines(row.name, ["name", "status", "attempts"])):
			enqueue_close(row.name)
		else:
			finish_box(row.name)


# ---------------------------------------------------------------- commercial


@frappe.whitelist(methods=["POST"])
def retry_box(box):
	"""Reintentar procesamiento: only lines not consumed (technical errors); business exceptions use their queues."""
	_require(reception.is_commercial)
	if frappe.db.get_value(BOX, box, "status") != FINALIZING:
		frappe.throw(_("La caja {0} no tiene procesamiento pendiente.").format(box))
	for name in frappe.get_all(LINE, filters={"box": box, "status": ERROR}, pluck="name"):
		frappe.db.set_value(LINE, name, "attempts", 0, update_modified=False)
	enqueue_close(box, after_commit=True)
	return box_detail(box)


@frappe.whitelist()
def list_incidents():
	"""Recepción > Cajas con incidencias: FINALIZING boxes with technical errors or without progress."""
	_require(reception.is_commercial)
	now = now_datetime()
	rows = frappe.get_all(BOX, filters={"status": FINALIZING}, fields=BOX_FIELDS, order_by="finalize_requested_on asc")
	return [row for row in rows if cint(row.error_lines) or row.last_error or is_stale(row.job_heartbeat, now)]


# ---------------------------------------------------------------- lists and history


def _boxes_matching(text):
	like = f"%{text}%"
	names = set(
		frappe.get_all(BOX, or_filters={"name": ("like", like), "external_ref": ("like", like)}, pluck="name")
	)
	names |= set(frappe.get_all(LINE, filters={"scanned_code": ("like", like)}, pluck="box", limit_page_length=500))
	names |= set(
		frappe.get_all(
			UNIT,
			filters={"box": ("is", "set")},
			or_filters={
				"encargo": ("like", like),
				"sales_order": ("like", like),
				"item": ("like", like),
				"customer": ("like", like),
			},
			pluck="box",
			limit_page_length=500,
		)
	)
	return names


def _boxes_of_user(user):
	names = set(frappe.get_all(LINE, filters={"scanned_by": user}, pluck="box", limit_page_length=1000))
	names |= set(
		frappe.get_all(
			BOX,
			or_filters={"opened_by": user, "finalize_requested_by": user, "cancelled_by": user},
			pluck="name",
		)
	)
	return names


@frappe.whitelist()
def list_boxes(view="open", search=None, status=None, date=None, user=None, limit=LIST_MAX):
	"""open: drafts and boxes being processed, any receptor (shift change, §23.8 #4). history: every box."""
	_require(can_read)
	filters = {}
	if view == "open":
		filters["status"] = ("in", [DRAFT, FINALIZING])
	elif status:
		filters["status"] = status
	if date:
		day = getdate(date)
		filters["opened_on"] = ("between", [f"{day} 00:00:00", f"{day} 23:59:59"])
	names = None
	text = (search or "").strip()
	if text:
		names = _boxes_matching(text)
	if user:
		users = _boxes_of_user(user)
		names = users if names is None else names & users
	if names is not None:
		if not names:
			return []
		filters["name"] = ("in", list(names))
	return frappe.get_all(
		BOX,
		filters=filters,
		fields=BOX_FIELDS,
		order_by="opened_on desc",
		limit_page_length=min(cint(limit) or LIST_MAX, 500),
	)


# ---------------------------------------------------------------- Spec 021


def closing_box_has_code(codes):
	"""Spec 018 §23.8 #9: from Finalizar until its line is processed, a purchase with that code is not editable."""
	codes = {code for code in codes if code}
	if not codes:
		return False
	boxes = frappe.get_all(BOX, filters={"status": FINALIZING}, pluck="name")
	if not boxes:
		return False
	rows = frappe.get_all(
		LINE,
		filters={"box": ("in", boxes), "status": ("in", [ACTIVE, ERROR]), "scanned_code": ("in", list(codes))},
		pluck="scanned_code",
	)
	return bool(exact_codes(rows, codes))
