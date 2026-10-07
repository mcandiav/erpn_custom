import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.encargo import demand  # noqa: E402
from erpn_custom.encargo import sales_order_encargo as soe  # noqa: E402
from erpn_custom.encargo import supply  # noqa: E402


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


class D(dict):
	__getattr__ = dict.get


def enc(**values):
	base = {"status": "Open", "requested_qty": 1, "source_type": "KNOWN_ITEM"}
	base.update(values)
	return D(base)


def event(name, source=demand.SHOPPER, qty=1, status=demand.COMMITTED, **values):
	return D(name=name, source_type=source, qty=qty, status=status, released_qty=0, **values)


def unit(event_name, status="POSTED", destination="ENCARGO"):
	return D(name=f"U-{event_name}-{status}", supply_event=event_name, status=status, destination=destination)


def buckets(row, events=(), units=()):
	return supply.encargo_buckets(row, demand.summarize(row.requested_qty, list(events), list(units)))


class SupplyCase(unittest.TestCase):
	def setUp(self):
		for target, name, value in (
			(supply, "flt", lambda v, *a, **k: float(v or 0)),
			(demand, "flt", lambda v, *a, **k: float(v or 0)),
			(demand.frappe, "_dict", D),
			(soe, "flt", lambda v, *a, **k: float(v or 0)),
			(soe, "_", lambda msg: msg),
			(soe.frappe, "throw", _throw),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)


class TestEncargoBuckets(SupplyCase):
	def test_pending_purchase(self):
		self.assertEqual(buckets(enc(requested_qty=2)), [(supply.PENDING, 2)])

	def test_barcode_exception_and_rejection(self):
		pending = [event("E1", barcode_exception_status="PENDING_APPROVAL")]
		rejected = [event("E1", status=demand.REJECTED, barcode_exception_status="REJECTED")]
		self.assertEqual(buckets(enc(), pending), [(supply.EXCEPTION, 1)])
		self.assertEqual(buckets(enc(), rejected), [(supply.PENDING, 1)])

	def test_purchase_splits_covered_reception_transit(self):
		row = enc(requested_qty=4)
		units = [unit("E1"), unit("E1", status="RECEIVED")]
		self.assertEqual(
			buckets(row, [event("E1", qty=4)], units),
			[(supply.COVERED, 1), (supply.RECEPTION, 1), (supply.PURCHASED, 2)],
		)

	def test_ov_328_direct_reception_and_stock_cover_the_line(self):
		row = enc(requested_qty=5)
		events = [event("D1", demand.DIRECT, qty=4, status=demand.RECEIVED), event("S1", demand.STOCK, status=demand.RECEIVED)]
		units = [unit("D1") for _ in range(4)]
		self.assertEqual(buckets(row, events, units), [(supply.COVERED, 5)])

	def test_partial_purchases_leave_residual_demand(self):
		row = enc(requested_qty=5)
		self.assertEqual(
			buckets(row, [event("E1", qty=2), event("E2", qty=1)]),
			[(supply.PURCHASED, 3), (supply.PENDING, 2)],
		)

	def test_materialized_units_leave_the_pending_line(self):
		row = enc(requested_qty=3, materialized_qty=1, source_type="UNKNOWN_ITEM")
		units = [unit("E1"), unit("E1")]
		self.assertEqual(buckets(row, [event("E1", qty=3)], units), [(supply.RECEIVED, 1), (supply.PURCHASED, 1)])
		done = enc(requested_qty=1, materialized_qty=1, source_type="UNKNOWN_ITEM")
		self.assertEqual(sum(q for _l, q in buckets(done, [event("E1")], [unit("E1")])), 0)

	def test_pre_018_reception_counts_as_covered(self):
		row = enc(requested_qty=2)
		self.assertEqual(buckets(row, [event("M1", demand.MIGRATION, qty=2, status=demand.RECEIVED)]), [(supply.COVERED, 2)])
		self.assertEqual(supply.COVERED, "Cubierto")


class TestLineBuckets(SupplyCase):
	def test_mixed_line_reconciles_with_qty(self):
		buckets = supply.line_buckets(3, [[(supply.PURCHASED, 2)]])
		self.assertEqual(buckets, [(supply.COVERED, 1), (supply.PURCHASED, 2)])
		self.assertEqual(sum(q for _l, q in buckets), 3)

	def test_cancelled_encargo_does_not_count(self):
		buckets = supply.line_buckets(2, [[(supply.CANCELLED, 2)], [(supply.PENDING, 1)]])
		self.assertEqual(buckets, [(supply.COVERED, 1), (supply.PENDING, 1)])

	def test_cancelled_order(self):
		self.assertEqual(supply.line_buckets(2, [[(supply.PENDING, 2)]], order_cancelled=True), [(supply.CANCELLED, 2)])

	def test_two_encargos_on_one_line_merge(self):
		buckets = supply.line_buckets(3, [[(supply.EXCEPTION, 1)], [(supply.PENDING, 1)]])
		self.assertEqual(buckets, [(supply.COVERED, 1), (supply.PENDING, 1), (supply.EXCEPTION, 1)])


class TestConfirmedShortfall(SupplyCase):
	def order(self, confirmed, shortfalls):
		doc = MagicMock()
		doc.items = [D(item_code=code, custom_encargo_qty=qty) for code, qty in shortfalls]
		doc.get = {"custom_shopper_qty_confirmed": confirmed}.get
		return doc

	def test_without_modal_is_skipped(self):
		soe.require_confirmed_shortfall(self.order("", [("A", 5)]))
		soe.require_confirmed_shortfall(self.order(None, [("A", 5)]))

	def test_same_figure_passes(self):
		soe.require_confirmed_shortfall(self.order("2", [("A", 1), ("B", 1), (soe.ENCARGO_PENDIENTE_ITEM, 3)]))

	def test_stock_changed_blocks(self):
		with self.assertRaises(_Throw) as ctx:
			soe.require_confirmed_shortfall(self.order("1", [("A", 2)]))
		self.assertIn("El stock cambió", str(ctx.exception))

	def test_zero_confirmed_but_now_short_blocks(self):
		with self.assertRaises(_Throw):
			soe.require_confirmed_shortfall(self.order("0", [("A", 1)]))


class TestStockSplit(SupplyCase):
	def test_split_is_shared_by_preview_and_submit(self):
		rows = [
			D(item_code="A", warehouse="W", qty=3, is_stock_item=1),
			D(item_code=soe.ENCARGO_PENDIENTE_ITEM, qty=2),
		]
		with patch.object(soe, "_bin_available", return_value=1), patch.object(
			soe, "allocate_available_across_rows", return_value=[(1, 2)]
		):
			split = soe.stock_split(rows, None)
		self.assertEqual(split[id(rows[0])], (1, 2))
		self.assertEqual(split[id(rows[1])], (0, 2))


if __name__ == "__main__":
	unittest.main()
