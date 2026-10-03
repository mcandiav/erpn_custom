from erpn_custom.chile.matching import NO_MATCH, classify_rut

KNOWN_PAYER = "Known Payer"

OWN_PRIMARY = "own_primary"
OTHER_PRIMARY = "other_primary"
SAME_ACTIVE = "same_active"
OTHER_ACTIVE = "other_active"


def resolve_payer(normalized, customers_by_rut, lookup_active):
	"""Customer.tax_id first, then the active Known Payer; returns (rule, customers, known_payer)."""
	rule, names = classify_rut(normalized, customers_by_rut)
	if rule != NO_MATCH or not normalized:
		return rule, names, None
	active = lookup_active(normalized)
	if not active:
		return NO_MATCH, [], None
	known_payer, customer = active
	return KNOWN_PAYER, [customer], known_payer


def lock_violation(customer, primary_owners, active_owner):
	owners = list(dict.fromkeys(primary_owners or []))
	if customer in owners:
		return OWN_PRIMARY, customer
	if owners:
		return OTHER_PRIMARY, owners[0]
	if active_owner and active_owner == customer:
		return SAME_ACTIVE, customer
	if active_owner:
		return OTHER_ACTIVE, active_owner
	return None, None


def active_rut_key(active, normalized):
	return normalized if active and normalized else None


def should_offer_learning(payer_rut, customer_rut, active_owner, customer):
	return bool(payer_rut) and payer_rut != customer_rut and active_owner != customer


def violation_message(code, rut, other):
	if code == OTHER_ACTIVE:
		return (
			f"El RUT pagador {rut} ya está asociado a {other}. Debe desactivar primero esa "
			"asociación antes de asignarlo a otro cliente."
		)
	if code == OTHER_PRIMARY:
		return (
			f"El RUT {rut} corresponde al RUT principal del cliente {other} y no puede "
			"registrarse como pagador de otro cliente."
		)
	if code == OWN_PRIMARY:
		return f"El RUT {rut} es el RUT principal de {other}; no se registra como pagador conocido."
	if code == SAME_ACTIVE:
		return f"El RUT pagador {rut} ya está registrado como pagador conocido de {other}."
	return ""


def learning_conflict_message(owner, customer):
	return (
		f"Este RUT de origen ya está registrado como pagador de {owner}. El depósito actual fue "
		f"asignado a {customer}, pero la relación permanente no fue modificada."
	)
