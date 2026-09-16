def flt_amount(value):
	try:
		return float(value or 0)
	except (TypeError, ValueError):
		return 0.0


def is_eligible_credit(row):
	deposit = flt_amount(row.get("deposit"))
	withdrawal = flt_amount(row.get("withdrawal"))
	if deposit <= 0 or withdrawal > 0:
		return False, "not_credit"
	if int(row.get("docstatus") or 0) == 2:
		return False, "cancelled"
	if (row.get("party_type") or "") != "Customer" or not row.get("party"):
		return False, "no_customer"
	return True, ""


def allocation_plan(payments, amount):
	remaining = flt_amount(amount)
	plan = []
	for payment in payments:
		if remaining <= 0:
			break
		available = flt_amount(payment.get("unallocated_amount"))
		if available <= 0:
			continue
		take = available if available <= remaining else remaining
		plan.append({"name": payment["name"], "amount": take})
		remaining = flt_amount(remaining - take)
	return plan, remaining


def sql_savepoint_name(prefix, docname):
	cleaned = "".join(ch if ch.isalnum() else "_" for ch in f"{prefix}_{docname}")
	return cleaned[:32]


def remaining_order_amount(grand_total, already_applied):
	pending = flt_amount(grand_total) - flt_amount(already_applied)
	return pending if pending > 0 else 0


def proposed_apply_amount(available, pending):
	available = flt_amount(available)
	pending = flt_amount(pending)
	if available <= 0 or pending <= 0:
		return 0
	return available if available <= pending else pending
