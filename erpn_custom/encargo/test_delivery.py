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
sys.modules.setdefault("frappe.utils.file_manager", MagicMock())

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM, delivery  # noqa: E402

MATRIZ = "Matriz - FRAG"
RECEPCION = "Recepcion Encargos - FRAG"


class D(dict):
	__getattr__ = dict.get


class Stop(Exception):
	pass


def throw(msg, *a, **k):
	raise Stop(msg)


def row(qty, so_detail="l1", warehouse=MATRIZ, idx=1, item_code="ITEM-1", order="OV-1"):
	return D(
		idx=idx,
		item_code=item_code,
		qty=qty,
		stock_qty=qty,
		warehouse=warehouse,
		so_detail=so_detail,
		against_sales_order=order,
	)


class TestExcess(unittest.TestCase):
	def setUp(self):
		patcher = patch.object(delivery, "flt", lambda v, *a, **k: float(v or 0))
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_only_reserved_quantity_is_deliverable(self):
		reserved = {("l1", MATRIZ): 1}
		self.assertEqual(delivery.excess([row(1)], reserved), [])
		self.assertEqual([held for _r, held in delivery.excess([row(3)], reserved)], [1])

	def test_rows_of_the_same_line_add_up(self):
		reserved = {("l1", MATRIZ): 2}
		problems = delivery.excess([row(1, idx=1), row(2, idx=2)], reserved)
		self.assertEqual([r.idx for r, _h in problems], [2])

	def test_reservation_counts_per_warehouse(self):
		reserved = {("l1", RECEPCION): 1, ("l1", MATRIZ): 1}
		self.assertEqual(delivery.excess([row(1, warehouse=RECEPCION), row(1, warehouse=MATRIZ, idx=2)], reserved), [])
		self.assertEqual(len(delivery.excess([row(2, warehouse=RECEPCION)], reserved)), 1)

	def test_unit_without_reservation_is_not_deliverable(self):
		self.assertEqual(len(delivery.excess([row(1)], {})), 1)


class TestHook(unittest.TestCase):
	def setUp(self):
		self.reserved = {}
		self.orders = {"OV-1"}
		for target, name, value in (
			(delivery, "flt", lambda v, *a, **k: float(v or 0)),
			(delivery, "_", lambda msg: msg),
			(delivery.frappe, "throw", throw),
			(delivery, "_orders_with_encargo", lambda orders: set(orders) & self.orders),
			(delivery, "_reserved", lambda lines: self.reserved),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def doc(self, *rows, is_return=0):
		return D(items=list(rows), is_return=is_return)

	def test_blocks_stock_available_without_reservation(self):
		self.reserved = {("l1", MATRIZ): 1}
		with self.assertRaises(Stop) as ctx:
			delivery.validate_reserved_delivery(self.doc(row(3)))
		self.assertIn("Asignar stock a demanda", str(ctx.exception))

	def test_reserved_delivery_passes(self):
		self.reserved = {("l1", RECEPCION): 1}
		delivery.validate_reserved_delivery(self.doc(row(1, warehouse=RECEPCION)))

	def test_orders_without_encargo_and_returns_are_standard(self):
		delivery.validate_reserved_delivery(self.doc(row(3, order="OV-2")))
		delivery.validate_reserved_delivery(self.doc(row(-3), is_return=1))

	def test_encargo_pendiente_is_left_to_spec_019(self):
		delivery.validate_reserved_delivery(self.doc(row(1, item_code=ENCARGO_PENDIENTE_ITEM)))


if __name__ == "__main__":
	unittest.main()
