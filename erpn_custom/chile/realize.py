import time

import frappe
from frappe.utils import flt, getdate, now_datetime

from erpn_custom.chile.realize_rules import is_eligible_credit

BATCH_SIZE = 50
LOCK_KEY = "erpn_custom:realize_lock"
LOCK_TTL = 1800
JOB_ID = "erpn_custom:realize_deposits"


def enqueue_realize_pending():
	if _job_running():
		return {"ok": False, "reason": "already_running"}
	frappe.enqueue(
		"erpn_custom.chile.realize.run_realize_pending",
		queue="long",
		timeout=LOCK_TTL,
		job_id=JOB_ID,
		deduplicate=True,
	)
	return {"ok": True, "job": JOB_ID}


def tick_from_scheduler():
	if not _pending_names(limit=1):
		return {"ok": True, "reason": "none"}
	if _job_running():
		return {"ok": False, "reason": "already_running"}
	return enqueue_realize_pending()


def run_realize_pending():
	if not _acquire_lock():
		return {"ok": False, "reason": "lock"}
	started = time.monotonic()
	try:
		metrics = realize_pending_attributed_deposits()
		metrics["duration_ms"] = int((time.monotonic() - started) * 1000)
		return metrics
	finally:
		_release_lock()


def realize_pending_attributed_deposits(limit=None):
	metrics = {"analyzed": 0, "realized": 0, "already": 0, "skipped": 0, "errors": 0}
	names = _pending_names(limit=limit)
	for offset in range(0, len(names), BATCH_SIZE):
		for name in names[offset : offset + BATCH_SIZE]:
			metrics["analyzed"] += 1
			try:
				result = realize_attributed_deposit(name)
			except Exception:
				metrics["errors"] += 1
				_mark_status(name, "Error", frappe.get_traceback()[:500])
				frappe.db.commit()
				continue
			status = (result or {}).get("result")
			if status == "realized":
				metrics["realized"] += 1
			elif status == "already_realized":
				metrics["already"] += 1
			elif status in ("skipped", "ineligible"):
				metrics["skipped"] += 1
			else:
				metrics["errors"] += 1
		frappe.db.commit()
	return metrics


def realize_attributed_deposit(bank_transaction_name):
	if not bank_transaction_name:
		return {"ok": False, "result": "skipped", "reason": "missing_name"}

	row = frappe.db.get_value(
		"Bank Transaction",
		bank_transaction_name,
		[
			"name",
			"party",
			"party_type",
			"deposit",
			"withdrawal",
			"status",
			"docstatus",
			"date",
			"transaction_id",
			"bank_account",
			"unallocated_amount",
			"custom_ingest_key",
			"custom_payment_entry",
			"reference_number",
		],
		as_dict=True,
	)
	if not row:
		return {"ok": False, "result": "skipped", "reason": "not_found", "name": bank_transaction_name}

	existing = _existing_payment_entry(row)
	if existing:
		_link_realized(row.name, existing, row.get("custom_ingest_key"))
		return {"ok": True, "result": "already_realized", "payment_entry": existing, "name": row.name}

	eligible, reason = is_eligible_credit(row)
	if not eligible:
		_mark_status(row.name, "Skipped", reason)
		return {"ok": True, "result": "ineligible", "reason": reason, "name": row.name}

	if flt(row.unallocated_amount) <= 0:
		_mark_status(row.name, "Skipped", "no_unallocated")
		return {"ok": True, "result": "skipped", "reason": "no_unallocated", "name": row.name}

	if int(row.docstatus or 0) == 0:
		frappe.get_doc("Bank Transaction", row.name).submit()

	from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
		create_payment_entry_bts,
	)

	posting_date = getdate(row.date) or getdate(now_datetime())
	savepoint = f"realize_{row.name}"[:50]
	frappe.db.savepoint(savepoint)
	payload = {
		"bank_transaction_name": row.name,
		"reference_number": (row.transaction_id or row.name)[:140],
		"reference_date": str(posting_date),
		"party_type": "Customer",
		"party": row.party,
		"posting_date": str(posting_date),
		"mode_of_payment": _mode_of_payment(),
		"cost_center": _company_cost_center(row.bank_account),
		"company_bank_account": row.bank_account,
	}
	try:
		try:
			create_payment_entry_bts(**payload)
		except TypeError:
			payload.pop("company_bank_account", None)
			create_payment_entry_bts(**payload)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		message = frappe.get_traceback()[:500]
		_mark_status(row.name, "Error", message)
		return {"ok": False, "result": "error", "reason": message, "name": row.name}

	payment_entry = _linked_payment_entry(row.name) or _existing_payment_entry(row)
	if not payment_entry:
		_mark_status(row.name, "Error", "payment_entry_not_linked")
		return {"ok": False, "result": "error", "reason": "payment_entry_not_linked", "name": row.name}

	_link_realized(row.name, payment_entry, row.get("custom_ingest_key"))
	return {"ok": True, "result": "realized", "payment_entry": payment_entry, "name": row.name}


def _existing_payment_entry(row):
	name = row.get("custom_payment_entry")
	if name and frappe.db.exists("Payment Entry", {"name": name, "docstatus": 1}):
		return name
	if frappe.db.has_column("Payment Entry", "custom_bank_transaction"):
		found = frappe.db.get_value(
			"Payment Entry",
			{"custom_bank_transaction": row.name, "docstatus": 1},
			"name",
		)
		if found:
			return found
	ingest_key = row.get("custom_ingest_key")
	if ingest_key and frappe.db.has_column("Payment Entry", "custom_ingest_key"):
		found = frappe.db.get_value(
			"Payment Entry",
			{"custom_ingest_key": ingest_key, "docstatus": 1, "payment_type": "Receive"},
			"name",
		)
		if found:
			return found
	return _linked_payment_entry(row.name)


def _linked_payment_entry(bank_transaction_name):
	if not frappe.db.exists("DocType", "Bank Transaction Payments"):
		return None
	rows = frappe.get_all(
		"Bank Transaction Payments",
		filters={"parent": bank_transaction_name, "payment_document": "Payment Entry"},
		fields=["payment_entry"],
		order_by="idx asc",
		limit=1,
	)
	if not rows:
		return None
	payment_entry = rows[0].payment_entry
	if payment_entry and frappe.db.exists("Payment Entry", {"name": payment_entry, "docstatus": 1}):
		return payment_entry
	return None


def _link_realized(bank_transaction_name, payment_entry, ingest_key=None):
	bt_values = {"custom_realization_status": "Realized"}
	if frappe.db.has_column("Bank Transaction", "custom_payment_entry"):
		bt_values["custom_payment_entry"] = payment_entry
	if frappe.db.has_column("Bank Transaction", "custom_realization_error"):
		bt_values["custom_realization_error"] = ""
	frappe.db.set_value("Bank Transaction", bank_transaction_name, bt_values, update_modified=True)
	pe_values = {}
	if frappe.db.has_column("Payment Entry", "custom_bank_transaction"):
		pe_values["custom_bank_transaction"] = bank_transaction_name
	if ingest_key and frappe.db.has_column("Payment Entry", "custom_ingest_key"):
		pe_values["custom_ingest_key"] = ingest_key
	if pe_values:
		frappe.db.set_value("Payment Entry", payment_entry, pe_values, update_modified=False)


def _mark_status(name, status, reason=""):
	values = {}
	if frappe.db.has_column("Bank Transaction", "custom_realization_status"):
		values["custom_realization_status"] = status
	if frappe.db.has_column("Bank Transaction", "custom_realization_error"):
		values["custom_realization_error"] = (reason or "")[:500]
	if values:
		frappe.db.set_value("Bank Transaction", name, values, update_modified=False)


def _pending_names(limit=None):
	fields = ["name"]
	if frappe.db.has_column("Bank Transaction", "custom_payment_entry"):
		fields.append("custom_payment_entry")
	rows = frappe.get_all(
		"Bank Transaction",
		filters=[
			["docstatus", "<", 2],
			["deposit", ">", 0],
			["party_type", "=", "Customer"],
			["party", "!=", ""],
		],
		fields=fields,
		order_by="date asc, name asc",
	)
	pending = []
	for row in rows:
		if row.get("custom_payment_entry"):
			continue
		pending.append(row.name)
		if limit and len(pending) >= limit:
			break
	return pending


def _mode_of_payment():
	try:
		return frappe.db.get_value("Mode of Payment", {"enabled": 1, "type": "Bank"}, "name")
	except Exception:
		return None


def _company_cost_center(bank_account):
	account = frappe.db.get_value("Bank Account", bank_account, "account")
	if not account:
		return None
	company = frappe.db.get_value("Account", account, "company")
	if not company:
		return None
	return frappe.db.get_value("Company", company, "cost_center")


def _job_running():
	try:
		from frappe.utils.background_jobs import is_job_enqueued

		return bool(is_job_enqueued(JOB_ID))
	except Exception:
		return False


def _acquire_lock(check_only=False):
	cache = frappe.cache()
	key = cache.make_key(LOCK_KEY)
	if check_only:
		return not bool(cache.get(key))
	try:
		return bool(cache.set(key, b"1", nx=True, ex=LOCK_TTL))
	except Exception:
		return False


def _release_lock():
	frappe.cache().delete_value(LOCK_KEY)
