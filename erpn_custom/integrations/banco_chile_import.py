import json
import time

import frappe
from frappe import _
from frappe.utils.background_jobs import enqueue, is_job_enqueued

from erpn_custom.chile.banco_chile_cartola import load_tabular_bytes, parse_cartola_rows, process_cartola_records
from erpn_custom.chile.ingest import _existing_names


class BancoChileStatementImportMixin:
	def start_import(self):
		if is_banco_chile_import(self):
			return enqueue_banco_chile_import(self)
		return super().start_import()


@frappe.whitelist()
def form_start_import(data_import):
	bsi = frappe.get_doc("Bank Statement Import", data_import)
	bsi.check_permission("write")
	if is_banco_chile_import(bsi):
		return enqueue_banco_chile_import(bsi)
	from erpnext.accounts.doctype.bank_statement_import.bank_statement_import import (
		form_start_import as core_form_start_import,
	)

	return core_form_start_import(data_import)


def is_banco_chile_import(doc):
	if not getattr(doc, "import_file", None):
		return False
	try:
		filename, content = _read_import_file(doc.import_file)
		rows = load_tabular_bytes(content, filename)
		parsed = parse_cartola_rows(rows)
	except Exception:
		return False
	return bool(parsed.get("ok"))


def enqueue_banco_chile_import(doc):
	if not doc.bank_account:
		frappe.throw(_("Seleccione una Cuenta bancaria"))
	run_now = frappe.in_test or frappe.conf.developer_mode
	job_id = f"bank_statement_import::{doc.name}"
	if run_now:
		run_banco_chile_import_job(doc.name)
		return True
	if not is_job_enqueued(job_id):
		enqueue(
			run_banco_chile_import_job,
			queue="default",
			timeout=6000,
			event="data_import",
			job_id=job_id,
			data_import=doc.name,
		)
	return True


def run_banco_chile_import_job(data_import):
	doc = frappe.get_doc("Bank Statement Import", data_import)
	summary = {
		"created": [],
		"skipped_duplicate": [],
		"rejected": [],
		"mapped": [],
	}
	try:
		if not doc.bank_account:
			frappe.throw(_("Seleccione una Cuenta bancaria"))
		filename, content = _read_import_file(doc.import_file)
		parsed = parse_cartola_rows(load_tabular_bytes(content, filename))
		if not parsed.get("ok"):
			frappe.throw(_("El archivo no es una cartola Banco de Chile reconocible"))
		account_currency = _account_currency(doc.bank_account)
		decisions = process_cartola_records(
			parsed["records"],
			doc.bank_account,
			lambda account, tid: _existing_names(account, tid),
		)
		total = len(decisions)
		if frappe.db.has_column("Bank Statement Import", "payload_count"):
			doc.db_set("payload_count", max(total, 0), update_modified=False)
		last_eta = 0
		for index, decision in enumerate(decisions, start=1):
			started = time.perf_counter()
			_apply_decision(doc, decision, account_currency, summary)
			last_eta = _import_eta(last_eta, time.perf_counter() - started, total - index)
			_publish_import_progress(doc.name, index, total, decision.get("result"), last_eta)
		status = _import_status(summary)
		_store_result(doc, summary, status)
		return {"ok": True, "status": status, "summary": _public_summary(summary)}
	except Exception:
		if not summary["created"] and not summary["skipped_duplicate"]:
			doc.db_set("status", "Error", update_modified=True)
			frappe.db.commit()
		doc.log_error("Banco de Chile statement import failed")
		raise
	finally:
		frappe.publish_realtime("data_import_refresh", {"data_import": doc.name})


def _apply_decision(doc, decision, account_currency, summary):
	result = decision["result"]
	if result == "skip_duplicate":
		summary["skipped_duplicate"].append(decision)
		_realize_existing(decision)
		return
	if result != "create":
		summary["rejected"].append(decision)
		return

	payload = decision["payload"]
	payload["currency"] = _resolve_currency(payload.get("currency"), account_currency)
	savepoint = f"bch_{decision['row_number']}"
	frappe.db.savepoint(savepoint)
	try:
		bt = frappe.get_doc(payload)
		bt.auto_set_party = lambda: None
		bt.insert()
		if doc.submit_after_import:
			bt.auto_set_party = lambda: None
			bt.submit()
		else:
			bt.db_set("status", "Unreconciled", update_modified=False)
		decision["name"] = bt.name
		summary["created"].append(decision)
		frappe.db.commit()
		_map_created(decision, summary)
	except Exception as exc:
		frappe.db.rollback(save_point=savepoint)
		message = str(exc)
		duplicate = "duplicate/skipped" in message or "Duplicate entry" in message
		decision["result"] = "skip_duplicate" if duplicate else "rejected"
		decision["reason"] = "duplicate/skipped" if duplicate else message[:500]
		summary["skipped_duplicate" if duplicate else "rejected"].append(decision)
		frappe.db.commit()


def _realize_existing(decision):
	from erpn_custom.chile.realize import realize_attributed_deposit

	name = decision.get("existing")
	if not name or str(name).startswith("in-file:"):
		return
	try:
		realization = realize_attributed_deposit(name)
		decision["realization"] = realization.get("result") if isinstance(realization, dict) else None
	except Exception as exc:
		decision["realization"] = "error"
		decision["realization_reason"] = str(exc)[:500]


def _map_created(decision, summary):
	from erpn_custom.chile.deposit_mapping import apply_party_for_bank_transaction

	name = decision.get("name")
	if not name:
		return
	try:
		mapping = apply_party_for_bank_transaction(name)
		decision["mapping"] = mapping.get("result") if isinstance(mapping, dict) else None
		realization = mapping.get("realization") if isinstance(mapping, dict) else None
		decision["realization"] = realization.get("result") if isinstance(realization, dict) else None
		summary["mapped"].append({"name": name, "result": decision["mapping"], "realization": decision["realization"]})
	except Exception as exc:
		decision["mapping"] = "error"
		summary["mapped"].append({"name": name, "result": "error", "reason": str(exc)[:500]})


def _import_eta(last_eta, processing_time, remaining):
	eta = processing_time * remaining
	if not last_eta or eta < last_eta:
		return eta
	return last_eta


def _publish_import_progress(data_import, current, total, result, eta):
	if not total:
		return
	frappe.publish_realtime(
		"data_import_progress",
		{
			"current": current,
			"total": total,
			"data_import": data_import,
			"success": result != "skip_duplicate",
			"skipping": result == "skip_duplicate",
			"eta": eta,
		},
		user=frappe.session.user,
	)


def _store_result(doc, summary, status):
	payload = _public_summary(summary)
	values = {"status": status}
	if frappe.db.has_column("Bank Statement Import", "custom_banco_chile_import_result"):
		values["custom_banco_chile_import_result"] = json.dumps(payload, default=str, ensure_ascii=False)
	doc.db_set(values, update_modified=True)
	frappe.db.commit()


def _public_summary(summary):
	return {
		"created": len(summary["created"]),
		"skipped_duplicate": len(summary["skipped_duplicate"]),
		"rejected": len(summary["rejected"]),
		"rows": [
			{
				"row": item.get("row_number"),
				"transaction_id": item.get("transaction_id"),
				"result": item.get("result"),
				"reason": item.get("reason"),
				"name": item.get("name"),
				"existing": item.get("existing"),
				"mapping": item.get("mapping"),
				"realization": item.get("realization"),
			}
			for item in summary["created"] + summary["skipped_duplicate"] + summary["rejected"]
		],
	}


def _import_status(summary):
	if summary["rejected"] and not summary["created"]:
		return "Error"
	if summary["rejected"]:
		return "Partial Success"
	return "Success"


def _account_currency(bank_account):
	account = frappe.db.get_value("Bank Account", bank_account, "account")
	if not account:
		return "CLP"
	return frappe.db.get_value("Account", account, "account_currency") or "CLP"


def _resolve_currency(file_currency, account_currency):
	if not file_currency:
		return account_currency
	if file_currency == account_currency:
		return file_currency
	if file_currency == "CLP" and account_currency == "CLP":
		return account_currency
	return account_currency


def _read_import_file(file_url):
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		frappe.throw(_("No se encontro el archivo de importacion"))
	file_doc = frappe.get_doc("File", name)
	return file_doc.file_name or file_url, file_doc.get_content()
