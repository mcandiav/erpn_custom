import sys
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM, inventory, materialization as m  # noqa: E402

NOW = datetime(2026, 10, 6, 10, 0)
WAREHOUSE = "Recepcion Encargos - FRAG"


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


class D(dict):
	__getattr__ = dict.get

	def __setattr__(self, key, value):
		self[key] = value


def technical(qty=3, **values):
	row = D(
		name="SOI-T",
		item_code=ENCARGO_PENDIENTE_ITEM,
		qty=qty,
		delivered_qty=0,
		billed_amt=0,
		rate=25000,
		price_list_rate=25000,
		discount_percentage=0,
		discount_amount=0,
		delivery_date="2026-10-20",
		cost_center="Main - FRAG",
		uom="Nos",
		stock_uom="Nos",
	)
	row.update(values)
	return row


def real(name="SOI-R", qty=1, item_code="ITEM-1", encargo="ENC-1", **values):
	row = D(
		name=name,
		item_code=item_code,
		qty=qty,
		warehouse=WAREHOUSE,
		uom="Nos",
		stock_uom="Nos",
		rate=25000,
		price_list_rate=25000,
		discount_percentage=0,
		discount_amount=0,
		delivered_qty=0,
		billed_amt=0,
		custom_encargo_origin=encargo,
	)
	row.update(values)
	return row


def encargo(**values):
	row = D(
		name="ENC-1",
		status="Open",
		source_type="UNKNOWN_ITEM",
		sales_order="SO-1",
		sales_order_item="SOI-T",
		requested_qty=3,
		materialized_qty=0,
	)
	row.update(values)
	return row


def unit(**values):
	row = D(
		name="RCU-1",
		encargo="ENC-1",
		sales_order="SO-1",
		item="ITEM-1",
		warehouse=WAREHOUSE,
		scan_event_id="scan-0001",
		received_by="r1@fragallardo.com",
		materialization_status=m.PENDING,
	)
	row.update(values)
	return row


class MaterializationCase(unittest.TestCase):
	def setUp(self):
		self.frappe = MagicMock()
		self.frappe.throw = _throw
		self.enc = encargo()
		self.order = SimpleNamespace(name="SO-1", docstatus=1, items=[technical()])
		self.mocks = {}
		for target, name, value in (
			(m, "frappe", self.frappe),
			(m, "_", lambda msg: msg),
			(m, "flt", lambda v, *a, **k: float(v or 0)),
			(m, "now_datetime", lambda: NOW),
			(m, "strip_html", lambda v: v),
			(m, "_lock_encargo", lambda name: self.enc),
			(m, "_lock_order", lambda name: self.order),
			(m, "_set_qty", MagicMock()),
			(m, "_insert_row", MagicMock(return_value="SOI-NEW")),
			(m, "_delete_row", MagicMock()),
			(m, "_refresh_order", MagicMock()),
			(m, "_set_encargo_qty", MagicMock()),
			(m, "_log", MagicMock()),
			(inventory, "reserve_unit", MagicMock(return_value=("SRE-9", None))),
		):
			patcher = patch.object(target, name, value)
			self.mocks[name] = patcher.start()
			self.addCleanup(patcher.stop)


class TestRules(MaterializationCase):
	def test_only_encargo_pendiente_lines_apply(self):
		self.assertTrue(m.applies(encargo()))
		self.assertFalse(m.applies(encargo(source_type="KNOWN_ITEM")))
		self.assertFalse(m.applies(None))

	def test_pending_never_negative(self):
		self.assertEqual(m.pending_qty(3, 1), 2)
		self.assertEqual(m.pending_qty(3, 5), 0)

	def test_order_problem(self):
		self.assertIsNone(m.order_problem(1, "Open"))
		self.assertIn("cancelada", m.order_problem(2, "Open"))
		self.assertIsNotNone(m.order_problem(0, "Open"))
		self.assertIn("cancelado", m.order_problem(1, "Cancelled"))

	def test_technical_problem(self):
		self.assertIsNone(m.technical_problem(technical(3), 3))
		self.assertIn("completo", m.technical_problem(technical(3), 0))
		self.assertIn("ya no existe", m.technical_problem(None, 3))
		self.assertIn("ya no es", m.technical_problem(technical(3, item_code="ITEM-1"), 3))
		for row in (technical(3, delivered_qty=1), technical(3, billed_amt=100), technical(2)):
			self.assertEqual(m.technical_problem(row, 3), m.incompatible_message())

	def test_compatible_row_needs_same_encargo_item_warehouse_and_price(self):
		t = technical()
		self.assertIsNotNone(m.compatible_row([real()], "ENC-1", "ITEM-1", t, WAREHOUSE))
		for row in (
			real(encargo="ENC-2"),
			real(item_code="ITEM-2"),
			real(warehouse="Matriz - FRAG"),
			real(uom="Caja"),
			real(rate=20000),
			real(discount_percentage=10),
		):
			self.assertIsNone(m.compatible_row([row], "ENC-1", "ITEM-1", t, WAREHOUSE))

	def test_real_row_inherits_sale_conditions_not_the_shopper_cost(self):
		values = m.real_row_values(technical(purchase_price=80), "ENC-1", WAREHOUSE)
		self.assertEqual((values["rate"], values["price_list_rate"], values["qty"]), (25000, 25000, 1))
		self.assertEqual((values["delivery_date"], values["cost_center"]), ("2026-10-20", "Main - FRAG"))
		self.assertEqual((values["custom_encargo_origin"], values["custom_encargo_source_row"]), ("ENC-1", "SOI-T"))
		self.assertEqual(values["warehouse"], WAREHOUSE)
		self.assertNotIn("purchase_price", values)

	def test_reverse_problem(self):
		self.assertIsNone(m.reverse_problem(real(qty=2, delivered_qty=1)))
		self.assertIsNotNone(m.reverse_problem(None))
		self.assertIn("entregada", m.reverse_problem(real(qty=1, delivered_qty=1)))
		self.assertIn("facturada", m.reverse_problem(real(qty=1, billed_amt=25000)))


class TestMaterialize(MaterializationCase):
	def test_first_unit_splits_the_line(self):
		u = unit()
		m.materialize(u)
		m._insert_row.assert_called_once()
		order, item, values = m._insert_row.call_args.args
		self.assertEqual((order, item, values["qty"], values["rate"]), ("SO-1", "ITEM-1", 1, 25000))
		m._set_qty.assert_called_once_with("SOI-T", 2)
		m._delete_row.assert_not_called()
		m._refresh_order.assert_called_once_with("SO-1")
		inventory.reserve_unit.assert_called_once_with("SO-1", "SOI-NEW", "ITEM-1", WAREHOUSE)
		m._set_encargo_qty.assert_called_once_with(self.enc, 1)
		self.assertEqual(
			(u.materialization_status, u.materialized_row, u.stock_reservation_entry, u.materialized_by),
			(m.MATERIALIZED, "SOI-NEW", "SRE-9", "r1@fragallardo.com"),
		)
		log = m._log.call_args
		self.assertEqual(log.args[1], m.MATERIALIZED)
		self.assertEqual((log.kwargs["technical_qty_before"], log.kwargs["technical_qty_after"]), (3, 2))

	def test_same_item_increments_its_line(self):
		self.enc = encargo(materialized_qty=1)
		self.order.items = [technical(2), real(qty=1)]
		m.materialize(unit())
		m._insert_row.assert_not_called()
		self.assertEqual(m._set_qty.call_args_list[0].args, ("SOI-R", 2))
		self.assertEqual(m._set_qty.call_args_list[1].args, ("SOI-T", 1))
		m._set_encargo_qty.assert_called_once_with(self.enc, 2)

	def test_other_encargo_line_is_never_merged(self):
		self.order.items = [technical(3), real(qty=1, encargo="ENC-2")]
		m.materialize(unit())
		m._insert_row.assert_called_once()

	def test_last_unit_removes_the_technical_line(self):
		self.enc = encargo(materialized_qty=2)
		self.order.items = [technical(1), real(qty=2)]
		m.materialize(unit())
		m._delete_row.assert_called_once_with("SO-1", "SOI-T")
		self.assertEqual(m._log.call_args.kwargs["technical_qty_after"], 0)

	def test_already_materialized_unit_is_a_noop(self):
		m.materialize(unit(materialization_status=m.MATERIALIZED))
		m._refresh_order.assert_not_called()
		m._log.assert_not_called()

	def _assert_error(self, text=None):
		u = unit()
		m.materialize(u)
		self.assertEqual(u.materialization_status, m.ERROR)
		if text:
			self.assertIn(text, u.materialization_message)
		self.frappe.db.rollback.assert_called_once_with(save_point="encargo_materialize")
		inventory.reserve_unit.assert_not_called()
		m._set_encargo_qty.assert_not_called()
		self.assertEqual(m._log.call_args.args[1], m.ERROR)
		return u

	def test_more_units_than_pending_is_an_error(self):
		self.enc = encargo(materialized_qty=3)
		self._assert_error("completo")
		m._insert_row.assert_not_called()

	def test_cancelled_order_is_an_error(self):
		self.order.docstatus = 2
		self._assert_error("cancelada")

	def test_delivered_or_billed_line_is_an_error(self):
		self.order.items = [technical(3, delivered_qty=1)]
		self._assert_error(m.incompatible_message())

	def test_erpnext_failure_keeps_the_unit_set_aside(self):
		m._refresh_order.side_effect = Exception("Límite de crédito")
		u = self._assert_error("Límite de crédito")
		self.assertIn("Apartado", u.reservation_note)

	def test_retry_after_error_materializes(self):
		m._refresh_order.side_effect = [Exception("Bloqueo"), None]
		u = unit()
		m.materialize(u)
		self.assertEqual(u.materialization_status, m.ERROR)
		m.materialize(u, "c1@fragallardo.com")
		self.assertEqual((u.materialization_status, u.materialized_by), (m.MATERIALIZED, "c1@fragallardo.com"))
		self.assertIsNone(u.materialization_message)


class TestReverse(MaterializationCase):
	def setUp(self):
		super().setUp()
		self.enc = encargo(materialized_qty=1)
		self.order.items = [technical(2), real(qty=1)]
		self.u = unit(materialization_status=m.MATERIALIZED, materialized_row="SOI-R")

	def test_unit_goes_back_to_encargo_pendiente(self):
		m.reverse(self.u, "c1@fragallardo.com", "Color distinto")
		self.assertEqual(m._set_qty.call_args.args, ("SOI-T", 3))
		m._delete_row.assert_called_once_with("SO-1", "SOI-R")
		m._refresh_order.assert_called_once_with("SO-1")
		m._set_encargo_qty.assert_called_once_with(self.enc, 0)
		self.assertEqual(m._log.call_args.args[1], m.REVERSED)
		self.assertEqual(self.u.materialization_status, m.REVERSED)

	def test_delivered_unit_is_not_reversed(self):
		self.order.items = [technical(2), real(qty=1, delivered_qty=1)]
		with self.assertRaises(_Throw):
			m.reverse(self.u, "c1@fragallardo.com")
		m._refresh_order.assert_not_called()

	def test_not_materialized_unit_is_ignored(self):
		m.reverse(unit(materialization_status=m.ERROR), "c1@fragallardo.com")
		m._refresh_order.assert_not_called()


class _Note:
	def __init__(self, items, new, is_return):
		self.items, self.new, self.is_return = items, new, is_return

	def get(self, field):
		return getattr(self, field, None)

	def is_new(self):
		return self.new

	def remove(self, row):
		self.items.remove(row)


class TestDeliveryBlock(MaterializationCase):
	def note(self, codes, new=True, is_return=0):
		return _Note([D(item_code=c, idx=i) for i, c in enumerate(codes, 1)], new, is_return)

	def test_pending_lines_are_dropped_from_a_new_note(self):
		doc = self.note(["ITEM-1", ENCARGO_PENDIENTE_ITEM, "ITEM-2"])
		m.block_pending_delivery(doc)
		self.assertEqual([(r.item_code, r.idx) for r in doc.items], [("ITEM-1", 1), ("ITEM-2", 2)])

	def test_only_pending_lines_cannot_be_delivered(self):
		with self.assertRaises(_Throw):
			m.block_pending_delivery(self.note([ENCARGO_PENDIENTE_ITEM]))
		with self.assertRaises(_Throw):
			m.block_pending_delivery(self.note(["ITEM-1", ENCARGO_PENDIENTE_ITEM], new=False))

	def test_returns_and_normal_notes_pass(self):
		m.block_pending_delivery(self.note([ENCARGO_PENDIENTE_ITEM], is_return=1))
		m.block_pending_delivery(self.note(["ITEM-1"]))


if __name__ == "__main__":
	unittest.main()
