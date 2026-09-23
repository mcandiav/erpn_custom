def flt(value):
	try:
		return float(value or 0)
	except (TypeError, ValueError):
		return 0.0


def available_to_sell(actual_qty, reserved_qty):
	return max(flt(actual_qty) - flt(reserved_qty), 0.0)


def split_qty(requested_qty, available_qty):
	requested = flt(requested_qty)
	available = max(flt(available_qty), 0.0)
	stock_committed = min(requested, available)
	encargo_qty = requested - stock_committed
	return stock_committed, encargo_qty


def allocate_available_across_rows(rows, available_qty):
	"""Allocate stock across rows sharing Item+Warehouse (order preserved).

	Each row dict needs: qty
	Returns list of (stock_committed_qty, encargo_qty).
	"""
	remaining = max(flt(available_qty), 0.0)
	out = []
	for row in rows:
		stock_committed, encargo_qty = split_qty(row.get("qty"), remaining)
		remaining = max(remaining - stock_committed, 0.0)
		out.append((stock_committed, encargo_qty))
	return out
