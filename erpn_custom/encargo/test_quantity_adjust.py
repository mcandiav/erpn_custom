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

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM, demand, quantity_adjust as qa  # noqa: E402

MATRIZ = "Matriz - FRAG"


class D(dict):
	__getattr__ = dict.get


class Stop(Exception):
	pass


def throw(msg, *a, **k):
	raise Stop(msg)


def order(docstatus=1):
	return D(name="OV-1", docstatus=docstatus, set_warehouse=MATRIZ)


def line(qty=3, item_code="ITEM-1", delivered=0, billed=0, **values):
	row = D(
		name="row1",
		idx=1,
		item_code=item_code,
		qty=qty,
		warehouse=MATRIZ,
		conversion_factor=1,
		delivered_qty=delivered,
		billed_amt=billed,
	)
	row.update(values)
	return row


def sre(name, reserved=1, delivered=0):
	return D(name=name, docstatus=1, warehouse=MATRIZ, reserved_qty=reserved, delivered_qty=delivered)


class Case(unittest.TestCase):
	def setUp(self):
		flt = lambda v, *a, **k: float(v or 0)  # noqa: E731
		self.state = D(paid=1000, available=0, encargo=None, totals=None, sres=[], expected=[])
		patches = [
			(qa, "flt", flt),
			(qa, "_", lambda msg: msg),
			(qa.frappe, "_dict", D),
			(qa.frappe, "throw", throw),
			(qa.frappe, "get_cached_value", lambda *a, **k: 1),
			(qa, "applied_to_order", lambda name: self.state.paid),
			(qa, "_available", lambda item, wh: self.state.available),
			(qa, "_line_encargo", lambda row, kind, lock: (self.state.encargo, self.state.totals)),
			(qa.reservations, "line_sres", lambda name: self.state.sres),
			(qa.reservations, "_line_inputs", lambda row: ([], self.state.expected)),
			(qa.reservations, "flt", flt),
			(demand, "flt", flt),
			(demand.frappe, "_dict", D),
		]
		for target, name, value in patches:
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def encargo(self, requested, events=(), units=()):
		self.state.encargo = D(name="ENC-1", status="Open", requested_qty=requested)
		self.state.totals = demand.summarize(requested, list(events), list(units))


def shopper(qty):
	return D(name=f"ev{qty}", source_type=demand.SHOPPER, status=demand.COMMITTED, qty=qty, released_qty=0)


class TestPureRules(unittest.TestCase):
	def test_increase_reserves_available_stock_first(self):
		self.assertEqual(qa.known_increase(3, 2), (2, 1))
		self.assertEqual(qa.known_increase(2, 5), (2, 0))
		self.assertEqual(qa.known_increase(2, 0), (0, 2))

	def test_decrease_cuts_unsourced_demand_then_reserved_stock(self):
		self.assertEqual(qa.known_decrease(1, 2, 1), (1, 0, 0))
		self.assertEqual(qa.known_decrease(3, 2, 1), (2, 1, 0))
		self.assertEqual(qa.known_decrease(4, 2, 1), (2, 1, 1))

	def test_who_adjusts(self):
		self.assertTrue(qa.can_adjust("seller@x", ["ComercialFRA"], ["seller@x"]))
		self.assertFalse(qa.can_adjust("other@x", ["ComercialFRA"], ["seller@x"]))
		self.assertTrue(qa.can_adjust("boss@x", ["Sales Manager"], ["seller@x"]))
		self.assertTrue(qa.can_adjust("admin@x", ["System Manager"], ["seller@x"]))

	def test_line_kinds(self):
		self.assertEqual(qa.line_kind(D(item_code="ITEM-1")), qa.KNOWN)
		self.assertEqual(qa.line_kind(D(item_code=ENCARGO_PENDIENTE_ITEM, custom_encargo="ENC-1")), qa.UNKNOWN)
		self.assertIsNone(qa.line_kind(D(item_code="ITEM-2", custom_encargo_origin="ENC-1")))

	def test_committed_reservations_exclude_units_and_allocations(self):
		sres = [sre("SRE-SUBMIT", 2), sre("SRE-UNIT")]
		self.assertEqual([s.name for s in qa.committed_sres(sres, [{"sre": "SRE-UNIT"}])], ["SRE-SUBMIT"])


class TestIncrease(Case):
	def test_known_increase_splits_stock_and_encargo(self):
		self.state.available = 1
		self.encargo(2)
		p = qa.plan(order(), line(3), 6)
		self.assertIsNone(p.problem)
		self.assertEqual((p.stock_part, p.encargo_part, p.encargo), (1, 2, "ENC-1"))

	def test_increase_after_purchase_grows_same_encargo(self):
		self.encargo(2, [shopper(2)])
		self.assertEqual(self.state.totals.pending_supply_qty, 0)
		p = qa.plan(order(), line(3), 4)
		self.assertEqual((p.encargo_part, p.encargo), (1, "ENC-1"))

	def test_line_without_encargo_gets_a_new_one(self):
		p = qa.plan(order(), line(2), 3)
		self.assertEqual((p.stock_part, p.encargo_part, p.encargo), (0, 1, None))
		self.assertIn("Encargo nuevo", qa.describe(p))

	def test_increase_requires_applied_payment(self):
		self.state.paid = 0
		p = qa.plan(order(), line(2), 3)
		self.assertIn("pago aplicado", p.problem)

	def test_unknown_increase_goes_to_its_encargo(self):
		self.encargo(2, [shopper(2)])
		row = line(2, item_code=ENCARGO_PENDIENTE_ITEM, custom_encargo="ENC-1")
		p = qa.plan(order(), row, 3)
		self.assertEqual((p.kind, p.encargo_part, p.stock_part), (qa.UNKNOWN, 1, 0))


class TestDecrease(Case):
	def test_known_decrease_cuts_pending_demand_first(self):
		self.encargo(2)
		self.state.sres = [sre("SRE-SUBMIT")]
		p = qa.plan(order(), line(3), 2)
		self.assertEqual((p.encargo_cut, p.stock_cut), (1, 0))

	def test_then_releases_reserved_stock(self):
		self.encargo(2, [shopper(1)])
		self.state.sres = [sre("SRE-SUBMIT")]
		p = qa.plan(order(), line(3), 1)
		self.assertIsNone(p.problem)
		self.assertEqual((p.encargo_cut, p.stock_cut), (1, 1))

	def test_never_below_purchased_or_received(self):
		self.encargo(2, [shopper(1)], [D(name="RCU-1", status="POSTED", destination="ENCARGO", supply_event="ev1")])
		self.state.sres = [sre("SRE-UNIT")]
		self.state.expected = [{"sre": "SRE-UNIT"}]
		p = qa.plan(order(), line(3), 1)
		self.assertIn("ya fue comprado", p.problem)
		self.assertIsNone(qa.plan(order(), line(3), 2).problem)

	def test_reservations_of_received_units_are_not_released(self):
		self.encargo(1, [], [D(name="RCU-1", status="POSTED", destination="ENCARGO")])
		self.state.sres = [sre("SRE-SUBMIT", 2), sre("SRE-UNIT")]
		self.state.expected = [{"sre": "SRE-UNIT"}]
		p = qa.plan(order(), line(3), 2)
		self.assertEqual([s.name for s in p.committed], ["SRE-SUBMIT"])
		self.assertEqual(p.stock_cut, 1)

	def test_delivered_and_billed_lines(self):
		self.assertIn("entregaron", qa.plan(order(), line(3, delivered=2), 1).problem)
		self.assertIn("facturada", qa.plan(order(), line(3, billed=100), 2).problem)

	def test_unknown_decrease_only_on_pending(self):
		self.encargo(3, [shopper(2)])
		row = line(3, item_code=ENCARGO_PENDIENTE_ITEM, custom_encargo="ENC-1")
		self.assertIsNone(qa.plan(order(), row, 2).problem)
		self.assertIn("sin compra", qa.plan(order(), row, 1).problem)


class TestGuards(Case):
	def test_materialized_line_and_draft_order(self):
		self.assertIn("materializado", qa.plan(order(), line(1, custom_encargo_origin="ENC-1"), 2).problem)
		self.assertIn("no está validada", qa.plan(order(0), line(1), 2).problem)
		self.assertIn("no cambia", qa.plan(order(), line(2), 2).problem)

	def test_update_items_blocked_with_encargo(self):
		with patch.object(qa, "has_encargo", lambda name: True):
			with self.assertRaises(Stop):
				qa.update_child_qty_rate("Sales Order", "[]", "OV-1")

	def test_update_items_allowed_without_encargo(self):
		standard = MagicMock(return_value="ok")
		controller = MagicMock(update_child_qty_rate=standard)
		with patch.object(qa, "has_encargo", lambda name: False), patch.dict(
			sys.modules, {"erpnext.controllers.accounts_controller": controller}
		):
			self.assertEqual(qa.update_child_qty_rate("Sales Order", "[]", "OV-2"), "ok")
		standard.assert_called_once_with("Sales Order", "[]", "OV-2", "items")


if __name__ == "__main__":
	unittest.main()
