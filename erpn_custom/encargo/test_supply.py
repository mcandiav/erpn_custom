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

from erpn_custom.encargo import sales_order_encargo as soe  # noqa: E402
from erpn_custom.encargo import supply  # noqa: E402


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


class D(dict):
	__getattr__ = dict.get


def enc(**values):
	base = {"status": "Open", "requested_qty": 1, "purchase_status": "PENDING"}
	base.update(values)
	return D(base)


class SupplyCase(unittest.TestCase):
	def setUp(self):
		for target, name, value in (
			(supply, "flt", lambda v, *a, **k: float(v or 0)),
			(soe, "flt", lambda v, *a, **k: float(v or 0)),
			(soe, "_", lambda msg: msg),
			(soe.frappe, "throw", _throw),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)


class TestEncargoBuckets(SupplyCase):
	def test_pending_purchase(self):
		self.assertEqual(supply.encargo_buckets(enc(requested_qty=2)), [(supply.PENDING, 2)])

	def test_barcode_exception_and_rejection(self):
		pending = enc(purchase_status="PURCHASED", barcode_exception_status="PENDING_APPROVAL")
		rejected = enc(purchase_status="PURCHASED", barcode_exception_status="REJECTED")
		self.assertEqual(supply.encargo_buckets(pending), [(supply.EXCEPTION, 1)])
		self.assertEqual(supply.encargo_buckets(rejected), [(supply.REJECTED, 1)])
		self.assertEqual(supply.REJECTED, "Compra rechazada - decide el vendedor")

	def test_purchase_splits_received_reception_transit(self):
		row = enc(requested_qty=4, purchase_status="PURCHASED", received_qty=1, barcode_exception_status="APPROVED")
		self.assertEqual(
			supply.encargo_buckets(row, waiting_units=1),
			[(supply.RECEIVED, 1), (supply.RECEPTION, 1), (supply.PURCHASED, 2)],
		)

	def test_pre_018_reception_counts_as_received(self):
		row = enc(requested_qty=2, purchase_status="PURCHASED", reception_status="RESOLVED_TO_ENC")
		self.assertEqual(supply.encargo_buckets(row)[0], (supply.RECEIVED, 2))


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
