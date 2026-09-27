"""Clean catalog reload: delete every Item and old Item Group that can be deleted.

Run from bench (System Manager context), always simulate first:
  bench --site <site> execute erpn_custom.catalog.purge.purge_catalog --kwargs "{'dry_run': 1}"
"""

import frappe

from erpn_custom.catalog.seed import normalize_text
from erpn_custom.catalog.tree import ROOT, iter_nodes
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM

KEEP_ITEMS = {ENCARGO_PENDIENTE_ITEM}
SAMPLE = 25


def purge_catalog(dry_run=1, vouchers=None):
	"""Drop cancelled stock vouchers, then delete Items and old groups; dry_run rolls everything back."""
	frappe.only_for("System Manager")
	dry_run = int(dry_run)
	report = {"dry_run": bool(dry_run), "vouchers": _drop_cancelled_vouchers(vouchers or [])}
	report["items"] = _delete_items()
	report["groups"] = _delete_old_groups()
	if dry_run:
		frappe.db.rollback()
	else:
		frappe.db.commit()
	return report


def _drop_cancelled_vouchers(vouchers):
	"""Remove the reversed ledger rows of cancelled Stock Reconciliations so their Items can go."""
	result = {}
	for name in vouchers:
		docstatus = frappe.db.get_value("Stock Reconciliation", name, "docstatus")
		if docstatus != 2:
			result[name] = f"omitido: docstatus={docstatus} (debe estar anulado)"
			continue
		filters = {"voucher_type": "Stock Reconciliation", "voucher_no": name, "is_cancelled": 1}
		sle = frappe.db.count("Stock Ledger Entry", filters)
		gle = frappe.db.count("GL Entry", filters)
		frappe.db.delete("Stock Ledger Entry", filters)
		frappe.db.delete("GL Entry", filters)
		frappe.db.delete("Repost Item Valuation", {"voucher_type": "Stock Reconciliation", "voucher_no": name})
		frappe.delete_doc("Stock Reconciliation", name, ignore_permissions=True, delete_permanently=True)
		result[name] = f"eliminado con {sle} movimientos de stock y {gle} asientos anulados"
	return result


def _delete_items():
	names = [n for n in frappe.get_all("Item", pluck="name", order_by="name") if n not in KEEP_ITEMS]
	blocked = {}
	for name in names:
		savepoint = "purge_item"
		frappe.db.savepoint(savepoint)
		try:
			frappe.delete_doc("Item", name, ignore_permissions=True, delete_permanently=True)
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			blocked[name] = _reason(e)
		frappe.clear_messages()
	return _summary(len(names), blocked)


def _delete_old_groups():
	keep = {normalize_text(name) for name, _parent, _is_group in iter_nodes()} | {normalize_text(ROOT)}
	groups = frappe.get_all("Item Group", fields=["name"], order_by="lft desc")
	candidates = [g.name for g in groups if normalize_text(g.name) not in keep]
	blocked = {}
	for name in candidates:
		savepoint = "purge_group"
		frappe.db.savepoint(savepoint)
		try:
			frappe.delete_doc("Item Group", name, ignore_permissions=True, delete_permanently=True)
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			blocked[name] = _reason(e)
		frappe.clear_messages()
	return _summary(len(candidates), blocked)


def _reason(error):
	return frappe.utils.strip_html(str(error))[:160]


def _summary(total, blocked):
	return {
		"candidatos": total,
		"eliminados": total - len(blocked),
		"bloqueados": len(blocked),
		"muestra_bloqueados": dict(list(blocked.items())[:SAMPLE]),
	}
