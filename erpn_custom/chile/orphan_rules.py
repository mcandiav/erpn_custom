MANUAL_RULE = "manual-attribution-v1"
MANUAL_REASON = "Asignación manual a Customer"


def orphan_eligibility(row):
	"""Pure eligibility for manual orphan assignment (not only Unreconciled)."""
	deposit = float(row.get("deposit") or 0)
	withdrawal = float(row.get("withdrawal") or 0)
	if deposit <= 0 or withdrawal > 0:
		return False, "not_credit"
	if int(row.get("docstatus") or 0) == 2:
		return False, "cancelled"
	if row.get("party"):
		return False, "already_assigned"
	return True, ""


def assignment_conflict(existing_party, customer):
	if not existing_party:
		return False
	return existing_party != customer
