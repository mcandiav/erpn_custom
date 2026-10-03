import frappe
from frappe.utils import escape_html, now_datetime

from erpn_custom.chile import known_payer_rules as rules
from erpn_custom.chile.matching import EXACT_TAX_ID, index_customers_by_normalized_tax_id
from erpn_custom.chile.rut import normalize_chilean_tax_id
from erpn_custom.identity.customer import get_chile_rut_customers
from erpn_custom.identity.filters import chile_rut_customer_filters

DOCTYPE = "Known Payer"
PAYMENT_ROLES = ("System Manager", "Accounts Manager", "Accounts User")


def resolve_customer_from_bank_payer(tax_id, customers_by_rut=None):
	normalized = normalize_chilean_tax_id(tax_id)
	if customers_by_rut is None:
		customers_by_rut = index_customers_by_normalized_tax_id(
			get_chile_rut_customers(fields=["name", "tax_id"]), normalize_chilean_tax_id
		)
	rule, names, known_payer = rules.resolve_payer(normalized, customers_by_rut, active_payer)
	resolved = rule in (EXACT_TAX_ID, rules.KNOWN_PAYER) and len(names) == 1
	return frappe._dict(
		normalized=normalized,
		method=rule,
		customers=names,
		customer=names[0] if resolved else None,
		known_payer=known_payer,
	)


def active_payer(normalized):
	if not normalized or not frappe.db.exists("DocType", DOCTYPE):
		return None
	row = frappe.db.get_value(DOCTYPE, {"active_rut_key": normalized}, ["name", "customer"], as_dict=True)
	return (row.name, row.customer) if row else None


def lock_active(name):
	"""Row lock shared with deactivate(): a relation being disabled is not used concurrently."""
	row = frappe.db.sql(f"select active from `tab{DOCTYPE}` where name=%s for update", name)
	return bool(row and row[0][0])


def mark_used(name):
	frappe.db.set_value(DOCTYPE, name, "last_used_on", now_datetime(), update_modified=False)


def primary_owners(normalized):
	customers = frappe.get_all(
		"Customer",
		filters=chile_rut_customer_filters(include_disabled=True),
		fields=["name", "tax_id"],
	)
	return [c.name for c in customers if normalize_chilean_tax_id(c.tax_id) == normalized]


def validate_known_payer(doc):
	normalized = normalize_chilean_tax_id(doc.payer_tax_id)
	if not normalized:
		frappe.throw(f"RUT pagador inválido: {escape_html(doc.payer_tax_id or '')}")
	doc.payer_tax_id_normalized = normalized
	if doc.is_new():
		doc.active = 1
		doc.confirmed_by = doc.confirmed_by or frappe.session.user
		doc.confirmed_on = doc.confirmed_on or now_datetime()
		doc.disabled_by = None
		doc.disabled_on = None
	elif not doc.flags.status_change and doc.has_value_changed("active"):
		frappe.throw("Use Desactivar asociación o Reactivar asociación.")
	doc.active_rut_key = rules.active_rut_key(doc.active, normalized)
	if not doc.active:
		return
	filters = {"active_rut_key": normalized}
	if not doc.is_new():
		filters["name"] = ["!=", doc.name]
	owner = frappe.db.get_value(DOCTYPE, filters, "customer")
	code, other = rules.lock_violation(doc.customer, primary_owners(normalized), owner)
	if code:
		frappe.throw(rules.violation_message(code, normalized, _label(other)), title="Pagador conocido")


def learning_offer(bank_transaction, customer):
	if not frappe.db.exists("DocType", DOCTYPE):
		return {"offer": False}
	payer_tax_id = frappe.db.get_value("Bank Transaction", bank_transaction, "custom_rut_del_pagador")
	payer = normalize_chilean_tax_id(payer_tax_id)
	customer_rut = normalize_chilean_tax_id(frappe.db.get_value("Customer", customer, "tax_id"))
	active = active_payer(payer)
	return {
		"offer": rules.should_offer_learning(payer, customer_rut, active[1] if active else None, customer),
		"payer_tax_id": payer_tax_id or "",
		"customer_name": frappe.db.get_value("Customer", customer, "customer_name") or customer,
	}


@frappe.whitelist()
def remember_payer(bank_transaction, customer):
	frappe.only_for(PAYMENT_ROLES)
	row = frappe.db.get_value(
		"Bank Transaction",
		bank_transaction,
		["name", "party", "party_type", "custom_rut_del_pagador", "bank_party_name"],
		as_dict=True,
	)
	if not row:
		frappe.throw(f"Bank Transaction inexistente: {escape_html(bank_transaction or '')}")
	if row.party_type != "Customer" or row.party != customer:
		return {
			"ok": False,
			"reason": "not_assigned",
			"message": f"El depósito {escape_html(row.name)} no está asignado a {_label(customer)}.",
		}
	normalized = normalize_chilean_tax_id(row.custom_rut_del_pagador)
	if not normalized:
		return {"ok": False, "reason": "invalid_rut", "message": "El depósito no trae un RUT de origen válido."}

	existing = _active_row(normalized)
	if existing:
		return _existing_result(existing, customer)
	code, other = rules.lock_violation(customer, primary_owners(normalized), None)
	if code:
		return {
			"ok": False,
			"reason": code,
			"message": rules.violation_message(code, escape_html(row.custom_rut_del_pagador), _label(other)),
		}

	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"customer": customer,
			"payer_tax_id": row.custom_rut_del_pagador,
			"payer_name": row.bank_party_name,
			"source": "Bank Reconciliation",
			"source_bank_transaction": row.name,
		}
	)
	try:
		doc.insert()
	except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
		frappe.db.rollback()
		frappe.clear_messages()
		existing = _active_row(normalized)
		if existing:
			return _existing_result(existing, customer)
		raise
	return {"ok": True, "result": "created", "known_payer": doc.name}


@frappe.whitelist()
def deactivate(name):
	frappe.only_for(rules.MANAGER_ROLES)
	lock_active(name)
	doc = frappe.get_doc(DOCTYPE, name)
	if not doc.active:
		return {"ok": True, "result": "already_inactive"}
	doc.update({"active": 0, "disabled_by": frappe.session.user, "disabled_on": now_datetime()})
	doc.flags.status_change = True
	doc.save()
	return {"ok": True, "result": "deactivated"}


@frappe.whitelist()
def reactivate(name):
	frappe.only_for(rules.MANAGER_ROLES)
	lock_active(name)
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.active:
		return {"ok": True, "result": "already_active"}
	doc.update({"active": 1, "disabled_by": None, "disabled_on": None})
	doc.flags.status_change = True
	doc.save()
	return {"ok": True, "result": "reactivated"}


@frappe.whitelist()
def customer_known_payers(customer):
	if not frappe.has_permission(DOCTYPE, "read"):
		return {"can_read": False, "rows": []}
	rows = frappe.get_all(
		DOCTYPE,
		filters={"customer": customer},
		fields=["name", "payer_tax_id", "payer_name", "active", "confirmed_on", "last_used_on"],
		order_by="active desc, confirmed_on desc",
	)
	return {"can_read": True, "can_create": bool(frappe.has_permission(DOCTYPE, "create")), "rows": rows}


def _active_row(normalized):
	return frappe.db.get_value(DOCTYPE, {"active_rut_key": normalized}, ["name", "customer"], as_dict=True)


def _existing_result(existing, customer):
	if existing.customer == customer:
		return {"ok": True, "result": "already_exists", "known_payer": existing.name}
	return {
		"ok": False,
		"reason": "conflict",
		"message": rules.learning_conflict_message(_label(existing.customer), _label(customer)),
		"known_payer": existing.name,
	}


def _label(customer):
	if not customer:
		return ""
	return escape_html(frappe.db.get_value("Customer", customer, "customer_name") or customer)
