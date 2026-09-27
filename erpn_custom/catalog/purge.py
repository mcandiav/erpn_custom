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
		reposts = _cancellation_reposts(name)
		pending = [r.name for r in reposts if r.status not in ("Completed", "Skipped", "Failed")]
		if pending:
			result[name] = f"omitido: {len(pending)} reprocesos de valorización aún en curso, reintentar más tarde"
			continue
		filters = {"voucher_type": "Stock Reconciliation", "voucher_no": name, "is_cancelled": 1}
		sle = frappe.db.count("Stock Ledger Entry", filters)
		gle = frappe.db.count("GL Entry", filters)
		frappe.db.delete("Stock Ledger Entry", filters)
		frappe.db.delete("GL Entry", filters)
		frappe.db.delete("Repost Item Valuation", {"voucher_type": "Stock Reconciliation", "voucher_no": name})
		if reposts:
			frappe.db.delete("Repost Item Valuation", {"name": ("in", [r.name for r in reposts])})
		frappe.delete_doc("Stock Reconciliation", name, ignore_permissions=True, delete_permanently=True)
		result[name] = (
			f"eliminado con {sle} movimientos de stock, {gle} asientos anulados "
			f"y {len(reposts)} reprocesos de valorización"
		)
	return result


def _cancellation_reposts(voucher):
	"""Item-wise reposts ERPNext creates on cancel carry no voucher, only item, warehouse and posting date."""
	reco = frappe.db.get_value("Stock Reconciliation", voucher, ["posting_date", "company"], as_dict=True)
	rows = frappe.get_all(
		"Stock Reconciliation Item", filters={"parent": voucher}, fields=["item_code", "warehouse"]
	)
	if not rows:
		return []
	candidates = frappe.get_all(
		"Repost Item Valuation",
		filters={
			"based_on": "Item and Warehouse",
			"posting_date": reco.posting_date,
			"company": reco.company,
			"item_code": ("in", list({r.item_code for r in rows})),
		},
		fields=["name", "status", "item_code", "warehouse"],
	)
	pairs = {(r.item_code, r.warehouse) for r in rows}
	return [c for c in candidates if (c.item_code, c.warehouse) in pairs]


def _delete_items():
	names = [n for n in frappe.get_all("Item", pluck="name", order_by="name") if n not in KEEP_ITEMS]
	blocked = {}
	for name in names:
		savepoint = "purge_item"
		frappe.db.savepoint(savepoint)
		try:
			frappe.delete_doc("Item", name, ignore_permissions=True, delete_permanently=True)
		except frappe.LinkExistsError:
			frappe.db.rollback(save_point=savepoint)
			blocked[name] = _item_links(name)
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			blocked[name] = _reason(e)
		frappe.clear_messages()
	return _summary(len(names), blocked)


def _item_links(name):
	"""Frappe replaces the Item link error with a generic hint, so list the real referencing documents."""
	from frappe.model.delete_doc import get_dynamic_linked_docs, get_linked_docs

	doc = frappe.get_doc("Item", name)
	links = get_linked_docs(doc) + get_dynamic_linked_docs(doc)
	refs = sorted(
		{f"{link['reference_doctype']} {link['reference_docname']}" for link in links}
		- {f"Item {name}"}
	)
	refs = [ref for ref in refs if not ref.startswith(("Bin ", "Item Price "))]
	return "vinculado con: " + ", ".join(refs[:3]) if refs else "vinculado (sin detalle)"


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
	motivos = {}
	for reason in blocked.values():
		prefix = "vinculado con: "
		if reason.startswith(prefix):
			key = reason[len(prefix) :].split(", ")[0].rsplit(" ", 1)[0]
		else:
			key = reason[:60]
		motivos[key] = motivos.get(key, 0) + 1
	return {
		"candidatos": total,
		"eliminados": total - len(blocked),
		"bloqueados": len(blocked),
		"motivos": motivos,
		"muestra_bloqueados": dict(list(blocked.items())[:SAMPLE]),
	}
