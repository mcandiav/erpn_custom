import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: 1 if int(v or 0) else 0
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


_frappe.throw = _throw
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.encargo.sales_order_encargo import (  # noqa: E402
	apply_stock_encargo_split,
	before_submit,
	validate_unknown_item_rows,
)
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM  # noqa: E402


class _Item(dict):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.__dict__ = self
		self.setdefault("idx", 1)
		self.setdefault("custom_encargo", None)
		self.setdefault("custom_stock_committed_qty", 0)
		self.setdefault("custom_encargo_qty", 0)

	def get(self, key, default=None):
		return super().get(key, default)


class _SO:
	doctype = "Sales Order"

	def __init__(self, items, set_warehouse="Matriz - FRAG"):
		self.items = items
		self.set_warehouse = set_warehouse
		self.name = "SAL-ORD-TEST"
		self.customer = "CUST"
		self.sales_team = []

	def get(self, key, default=None):
		return getattr(self, key, default)


class TestApplySplit(unittest.TestCase):
	@patch("erpn_custom.encargo.sales_order_encargo._bin_available", return_value=5.0)
	@patch("erpn_custom.encargo.sales_order_encargo._is_stock_item", return_value=1)
	def test_known_item_full_stock(self, _stock, _bin):
		row = _Item(item_code="ITEM-A", warehouse="Matriz - FRAG", qty=2, name="r1")
		doc = _SO([row])
		apply_stock_encargo_split(doc)
		self.assertEqual(row.custom_stock_committed_qty, 2)
		self.assertEqual(row.custom_encargo_qty, 0)

	@patch("erpn_custom.encargo.sales_order_encargo._bin_available", return_value=1.0)
	@patch("erpn_custom.encargo.sales_order_encargo._is_stock_item", return_value=1)
	def test_known_item_partial(self, _stock, _bin):
		row = _Item(item_code="ITEM-A", warehouse="Matriz - FRAG", qty=3, name="r1")
		doc = _SO([row])
		apply_stock_encargo_split(doc)
		self.assertEqual(row.custom_stock_committed_qty, 1)
		self.assertEqual(row.custom_encargo_qty, 2)

	@patch("erpn_custom.encargo.sales_order_encargo._bin_available", return_value=0.0)
	@patch("erpn_custom.encargo.sales_order_encargo._is_stock_item", return_value=1)
	def test_known_item_zero_stock(self, _stock, _bin):
		row = _Item(item_code="ITEM-A", warehouse="Matriz - FRAG", qty=1, name="r1")
		doc = _SO([row])
		apply_stock_encargo_split(doc)
		self.assertEqual(row.custom_stock_committed_qty, 0)
		self.assertEqual(row.custom_encargo_qty, 1)

	def test_unknown_item_row(self):
		row = _Item(item_code=ENCARGO_PENDIENTE_ITEM, warehouse=None, qty=2, name="r1")
		doc = _SO([row])
		apply_stock_encargo_split(doc)
		self.assertEqual(row.custom_stock_committed_qty, 0)
		self.assertEqual(row.custom_encargo_qty, 2)

	@patch("erpn_custom.encargo.sales_order_encargo._bin_available", return_value=3.0)
	@patch("erpn_custom.encargo.sales_order_encargo._is_stock_item", return_value=1)
	def test_aggregate_same_item_warehouse(self, _stock, _bin):
		r1 = _Item(item_code="ITEM-A", warehouse="Matriz - FRAG", qty=2, name="r1", idx=1)
		r2 = _Item(item_code="ITEM-A", warehouse="Matriz - FRAG", qty=2, name="r2", idx=2)
		doc = _SO([r1, r2])
		apply_stock_encargo_split(doc)
		self.assertEqual(r1.custom_stock_committed_qty, 2)
		self.assertEqual(r1.custom_encargo_qty, 0)
		self.assertEqual(r2.custom_stock_committed_qty, 1)
		self.assertEqual(r2.custom_encargo_qty, 1)


class TestValidateUnknown(unittest.TestCase):
	def test_pending_without_encargo_throws(self):
		row = _Item(item_code=ENCARGO_PENDIENTE_ITEM, qty=1, name="r1", custom_encargo=None)
		doc = _SO([row])
		with self.assertRaises(Exception):
			validate_unknown_item_rows(doc)

	def test_pending_with_encargo_ok(self):
		row = _Item(item_code=ENCARGO_PENDIENTE_ITEM, qty=1, name="r1", custom_encargo="ENC-1")
		doc = _SO([row])
		validate_unknown_item_rows(doc)


_MOD = "erpn_custom.encargo.sales_order_encargo"


@patch(f"{_MOD}.ensure_encargos_for_known_shortfalls")
@patch(f"{_MOD}.validate_unknown_item_rows")
@patch(f"{_MOD}.apply_stock_encargo_split")
class TestSubmitGates(unittest.TestCase):
	def setUp(self):
		# Another test module may have registered its own frappe mock first.
		for patcher in (
			patch(f"{_MOD}.frappe.throw", side_effect=_throw),
			patch(f"{_MOD}._", side_effect=lambda msg: msg),
		):
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_empty_order_blocked_before_any_effect(self, split, unknown, shortfalls):
		with patch(f"{_MOD}.applied_to_order", return_value=50000.0) as applied:
			with self.assertRaises(_Throw) as ctx:
				before_submit(_SO([]))
		self.assertIn("al menos un producto o Encargo", str(ctx.exception))
		applied.assert_not_called()
		split.assert_not_called()
		shortfalls.assert_not_called()

	def test_no_applied_payment_blocked_before_any_effect(self, split, unknown, shortfalls):
		row = _Item(item_code="ITEM-A", warehouse="Matriz - FRAG", qty=1, name="r1")
		with patch(f"{_MOD}.applied_to_order", return_value=0.0) as applied:
			with self.assertRaises(_Throw) as ctx:
				before_submit(_SO([row]))
		self.assertIn("pago aplicado", str(ctx.exception))
		applied.assert_called_once_with("SAL-ORD-TEST")
		split.assert_not_called()
		unknown.assert_not_called()
		shortfalls.assert_not_called()

	def test_partial_payment_passes_gates(self, split, unknown, shortfalls):
		row = _Item(item_code="ITEM-A", warehouse="Matriz - FRAG", qty=1, name="r1")
		doc = _SO([row])
		with patch(f"{_MOD}.applied_to_order", return_value=10000.0):
			before_submit(doc)
		split.assert_called_once_with(doc)
		unknown.assert_called_once_with(doc)
		shortfalls.assert_called_once_with(doc)


if __name__ == "__main__":
	unittest.main()
