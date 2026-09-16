import time

import frappe
from frappe.utils import now_datetime

from erpn_custom.chile.matching import CONFLICT, EXACT_TAX_ID, NO_MATCH, classify_rut, index_customers_by_normalized_tax_id
from erpn_custom.chile.rut import normalize_chilean_tax_id
from erpn_custom.chile.schedule import interval_due

BATCH_SIZE = 200
LOCK_KEY = "erpn_custom:deposit_mapping_lock"
LOCK_TTL = 1800
JOB_ID = "erpn_custom:deposit_mapping"
RULE_VERSION = "exact-tax-id-v1"
ELIGIBLE_STATUSES = ("Unreconciled",)

ALLOWED_ROLES = ("System Manager", "Accounts Manager", "Accounts User")


def enqueue_from_scheduler():
    enqueue_deposit_mapping(source="Scheduler", requested_by="Scheduler")


def tick_from_scheduler():
    enabled, interval_minutes = _mapping_settings()
    if not enabled:
        return {"ok": False, "reason": "disabled"}
    last = _last_run("Scheduler")
    if last and last.status in ("Queued", "Running"):
        return {"ok": False, "reason": "already_running", "run": last.name}
    last_finished = last.finished_at if last else None
    if not interval_due(last_finished, interval_minutes, now_datetime()):
        return {"ok": False, "reason": "interval"}
    return enqueue_deposit_mapping(source="Scheduler", requested_by="Scheduler")


def apply_party_for_bank_transaction(bank_transaction_name):
    """Idempotent Exact Tax ID mapping for one Bank Transaction.

    Same engine used by the Pagos de Clientes button, the interval job, and
    Banco de Chile ingestion after the Bank Transaction exists.
    """
    if not bank_transaction_name:
        return {"ok": False, "result": "skipped", "reason": "missing_name"}

    values = frappe.db.get_value(
        "Bank Transaction",
        bank_transaction_name,
        [
            "name",
            "party",
            "party_type",
            "reference_number",
            "custom_rut_del_pagador",
            "bank_party_name",
            "transaction_id",
            "deposit",
            "withdrawal",
            "status",
            "docstatus",
        ],
        as_dict=True,
    )
    if not values:
        return {"ok": False, "result": "skipped", "reason": "not_found", "name": bank_transaction_name}
    if values.docstatus == 2 or values.status not in ELIGIBLE_STATUSES or not (values.deposit or 0):
        return {"ok": True, "result": "skipped_ineligible", "name": bank_transaction_name}
    if values.party:
        return {"ok": True, "result": "already_mapped", "party": values.party, "name": bank_transaction_name}
    if not _acquire_lock():
        return {"ok": False, "result": "deferred", "reason": "lock", "name": bank_transaction_name}

    run = None
    try:
        run = frappe.get_doc(
            {
                "doctype": "Deposit Mapping Run",
                "source": "API",
                "status": "Running",
                "requested_by": (getattr(frappe.session, "user", None) or "API"),
                "rule_version": RULE_VERSION,
                "started_at": now_datetime(),
                "job_id": f"{JOB_ID}:api:{bank_transaction_name}",
            }
        )
        run.insert(ignore_permissions=True)
        frappe.db.commit()
        customers = frappe.get_all("Customer", filters={"disabled": 0}, fields=["name", "tax_id"])
        customers_by_rut = index_customers_by_normalized_tax_id(customers, normalize_chilean_tax_id)
        result = _map_one(values, customers_by_rut, run.name)
        run.update(
            {
                "analyzed_count": 1,
                "mapped_count": int(result == "mapped_count"),
                "already_mapped_count": int(result == "already_mapped_count"),
                "no_match_count": int(result == "no_match_count"),
                "conflict_count": int(result == "conflict_count"),
                "error_count": 0,
                "status": "Success",
                "finished_at": now_datetime(),
            }
        )
        run.save(ignore_permissions=True)
        frappe.db.commit()
        return {
            "ok": True,
            "result": result.replace("_count", ""),
            "run": run.name,
            "name": bank_transaction_name,
        }
    except Exception:
        if run and run.name:
            frappe.db.set_value(
                "Deposit Mapping Run",
                run.name,
                {
                    "status": "Failed",
                    "error_summary": frappe.get_traceback()[:500],
                    "finished_at": now_datetime(),
                },
            )
            frappe.db.commit()
        return {
            "ok": False,
            "result": "error",
            "name": bank_transaction_name,
            "run": run.name if run else None,
        }
    finally:
        _release_lock()


def enqueue_deposit_mapping(source="Manual", requested_by=None):
    running = frappe.db.exists("Deposit Mapping Run", {"status": ["in", ["Queued", "Running"]]})
    if running:
        return {"ok": False, "reason": "already_running", "run": running}

    run = frappe.get_doc(
        {
            "doctype": "Deposit Mapping Run",
            "source": source,
            "status": "Queued",
            "requested_by": requested_by or frappe.session.user,
            "rule_version": RULE_VERSION,
        }
    )
    run.insert(ignore_permissions=True)
    frappe.db.commit()

    frappe.enqueue(
        "erpn_custom.chile.deposit_mapping.run_deposit_mapping",
        queue="long",
        timeout=LOCK_TTL,
        job_id=JOB_ID,
        deduplicate=True,
        run_name=run.name,
    )
    return {"ok": True, "run": run.name}


def run_deposit_mapping(run_name=None):
    if not _acquire_lock():
        if run_name:
            frappe.db.set_value(
                "Deposit Mapping Run",
                run_name,
                {"status": "Failed", "error_summary": "Lock activo; no se solapa con otro run."},
            )
            frappe.db.commit()
        return

    started = time.monotonic()
    run = None
    try:
        if run_name:
            run = frappe.get_doc("Deposit Mapping Run", run_name)
        else:
            run = frappe.get_doc(
                {
                    "doctype": "Deposit Mapping Run",
                    "source": "Scheduler",
                    "status": "Queued",
                    "requested_by": "Scheduler",
                    "rule_version": RULE_VERSION,
                }
            )
            run.insert(ignore_permissions=True)

        run.status = "Running"
        run.started_at = now_datetime()
        run.job_id = JOB_ID
        run.save(ignore_permissions=True)
        frappe.db.commit()

        metrics = _process_batches(run)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if metrics["error_count"] and (metrics["mapped_count"] or metrics["no_match_count"] or metrics["conflict_count"]):
            status = "Partial"
        elif metrics["error_count"] and not metrics["mapped_count"]:
            status = "Failed"
        else:
            status = "Success"

        run.update(metrics)
        run.status = status
        run.finished_at = now_datetime()
        run.duration_ms = elapsed_ms
        run.save(ignore_permissions=True)
        frappe.db.commit()
        return run.name
    except Exception:
        frappe.db.rollback()
        if run_name:
            frappe.db.set_value(
                "Deposit Mapping Run",
                run_name,
                {
                    "status": "Failed",
                    "finished_at": now_datetime(),
                    "error_summary": frappe.get_traceback(),
                },
            )
            frappe.db.commit()
        raise
    finally:
        _release_lock()


def get_pagos_clientes_data(exception_start=0, exception_limit=50):
    pending = frappe.db.count(
        "Bank Transaction",
        filters=_eligible_filters(),
    )
    last_manual = _last_run("Manual")
    last_scheduler = _last_run("Scheduler")
    last_api = _last_run("API")
    last_any = _last_run(None)
    enabled, interval_minutes = _mapping_settings()
    exceptions = frappe.get_all(
        "Bank Transaction",
        filters=_eligible_filters(),
        fields=[
            "name",
            "date",
            "transaction_id",
            "bank_party_name",
            "custom_rut_del_pagador",
            "deposit",
            "custom_banco_origen",
            "custom_mapping_status",
            "unallocated_amount",
        ],
        order_by="date desc, name desc",
        start=exception_start,
        page_length=exception_limit,
    )
    return {
        "pending": pending,
        "running": bool(frappe.db.exists("Deposit Mapping Run", {"status": ["in", ["Queued", "Running"]]})),
        "last_run": last_any,
        "last_manual": last_manual,
        "last_scheduler": last_scheduler,
        "last_api": last_api,
        "scheduler_enabled": enabled,
        "interval_minutes": interval_minutes,
        "exceptions": exceptions,
    }


def _process_batches(run):
    metrics = {
        "analyzed_count": 0,
        "mapped_count": 0,
        "already_mapped_count": 0,
        "no_match_count": 0,
        "conflict_count": 0,
        "error_count": 0,
        "error_summary": "",
    }
    customers = frappe.get_all("Customer", filters={"disabled": 0}, fields=["name", "tax_id"])
    customers_by_rut = index_customers_by_normalized_tax_id(customers, normalize_chilean_tax_id)
    eligible_names = frappe.get_all(
        "Bank Transaction",
        filters=_eligible_filters(),
        pluck="name",
        order_by="date asc, name asc",
    )
    errors = []
    for offset in range(0, len(eligible_names), BATCH_SIZE):
        chunk = eligible_names[offset : offset + BATCH_SIZE]
        rows = frappe.get_all(
            "Bank Transaction",
            filters={"name": ["in", chunk]},
            fields=[
                "name",
                "party",
                "party_type",
                "reference_number",
                "custom_rut_del_pagador",
                "bank_party_name",
                "transaction_id",
                "deposit",
                "withdrawal",
                "status",
                "docstatus",
            ],
        )
        by_name = {row.name: row for row in rows}
        for name in chunk:
            row = by_name.get(name)
            if not row:
                continue
            metrics["analyzed_count"] += 1
            try:
                result = _map_one(row, customers_by_rut, run.name)
                metrics[result] += 1
            except Exception:
                metrics["error_count"] += 1
                err = f"{row.name}: {frappe.get_traceback()}"
                errors.append(err[:500])
                _mark_status(row.name, "Error")
        frappe.db.commit()
    if errors:
        metrics["error_summary"] = "\n".join(errors[:20])
    return metrics


def _map_one(row, customers_by_rut, run_name):
    if row.party:
        return "already_mapped_count"
    normalized = normalize_chilean_tax_id(row.custom_rut_del_pagador)
    _set_normalized(row.name, normalized)
    rule, names = classify_rut(normalized, customers_by_rut)
    if rule == EXACT_TAX_ID:
        _apply_customer(row, names[0], run_name)
        return "mapped_count"
    if rule == CONFLICT:
        _mark_status(row.name, CONFLICT)
        return "conflict_count"
    _mark_status(row.name, NO_MATCH)
    return "no_match_count"


def _apply_customer(row, customer, run_name):
    from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
        update_bank_transaction,
    )

    before = frappe.db.get_value(
        "Bank Transaction",
        row.name,
        [
            "bank_party_name",
            "custom_rut_del_pagador",
            "transaction_id",
            "deposit",
            "withdrawal",
            "description",
            "allocated_amount",
            "unallocated_amount",
        ],
        as_dict=True,
    )
    update_bank_transaction(
        bank_transaction_name=row.name,
        reference_number=row.reference_number or "",
        party_type="Customer",
        party=customer,
    )
    after = frappe.db.get_value(
        "Bank Transaction",
        row.name,
        [
            "party_type",
            "party",
            "bank_party_name",
            "custom_rut_del_pagador",
            "transaction_id",
            "deposit",
            "withdrawal",
            "description",
            "allocated_amount",
            "unallocated_amount",
        ],
        as_dict=True,
    )
    if after.party_type != "Customer" or after.party != customer:
        frappe.throw(f"No se persistio party en {row.name}")
    for field in (
        "bank_party_name",
        "custom_rut_del_pagador",
        "transaction_id",
        "deposit",
        "withdrawal",
        "description",
        "allocated_amount",
        "unallocated_amount",
    ):
        if before.get(field) != after.get(field):
            frappe.throw(f"Se altero evidencia {field} en {row.name}")
    frappe.db.set_value(
        "Bank Transaction",
        row.name,
        {
            "custom_attribution_rule": EXACT_TAX_ID,
            "custom_attribution_run": run_name,
            "custom_mapping_status": "Mapped",
        },
        update_modified=True,
    )


def _set_normalized(name, normalized):
    frappe.db.set_value("Bank Transaction", name, "custom_rut_pagador_normalizado", normalized or "", update_modified=False)


def _mark_status(name, status):
    frappe.db.set_value("Bank Transaction", name, "custom_mapping_status", status, update_modified=False)


def _mapping_settings():
    if not frappe.db.exists("DocType", "Deposit Mapping Settings"):
        return True, 15
    enabled = frappe.db.get_single_value("Deposit Mapping Settings", "enabled")
    interval = frappe.db.get_single_value("Deposit Mapping Settings", "interval_minutes")
    if enabled is None:
        enabled = 1
    try:
        minutes = int(interval)
    except (TypeError, ValueError):
        minutes = 15
    return bool(enabled), max(minutes, 1)


def _eligible_filters():
    return [
        ["docstatus", "<", 2],
        ["status", "in", list(ELIGIBLE_STATUSES)],
        ["deposit", ">", 0],
        ["party", "in", ["", None]],
    ]


def _last_run(source):
    filters = {}
    if source:
        filters["source"] = source
    rows = frappe.get_all(
        "Deposit Mapping Run",
        filters=filters,
        fields=[
            "name",
            "source",
            "status",
            "started_at",
            "finished_at",
            "duration_ms",
            "analyzed_count",
            "mapped_count",
            "already_mapped_count",
            "no_match_count",
            "conflict_count",
            "error_count",
        ],
        order_by="creation desc",
        limit=1,
    )
    return rows[0] if rows else None


def _acquire_lock():
    cache = frappe.cache()
    if cache.get_value(LOCK_KEY):
        return False
    cache.set_value(LOCK_KEY, "1", expires_in_sec=LOCK_TTL)
    return True


def _release_lock():
    frappe.cache().delete_value(LOCK_KEY)
