"""Spec 020 §23 / §25: whole sequences over the same pure rules the services run under lock."""

import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.validate_and_sanitize_search_inputs = lambda f: f
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)
sys.modules.setdefault("frappe.utils.file_manager", MagicMock())

from erpn_custom.encargo import demand, reception, shopper  # noqa: E402

CODE = "191267529486"
ITEM = "ITEM-1"


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


class D(dict):
	__getattr__ = dict.get


def purchase(n, shopper_user, qty=1, **values):
	row = D(
		name=f"EV-{n}",
		idx=n,
		source_type=demand.SHOPPER,
		status=demand.COMMITTED,
		qty=qty,
		released_qty=0,
		request_id=f"REQ-{n}",
		shopper_user=shopper_user,
		purchase_barcode=CODE,
	)
	row.update(values)
	return row


def direct(n):
	return D(name=f"EV-{n}", idx=n, source_type=demand.DIRECT, status=demand.RECEIVED, qty=1, released_qty=0)


def unit(event):
	return D(name=f"U-{event.name}", supply_event=event.name, status="POSTED", destination="ENCARGO")


ENCARGO = D(name="ENC-1", status="Open", source_type="KNOWN_ITEM", expected_item=ITEM, requested_qty=4)


class AcceptanceCase(unittest.TestCase):
	def setUp(self):
		flt = lambda v, *a, **k: float(v or 0)  # noqa: E731
		for target, name, value in (
			(demand, "flt", flt),
			(demand.frappe, "_dict", D),
			(shopper, "flt", flt),
			(shopper, "_", lambda msg: msg),
			(shopper.frappe, "throw", _throw),
			(reception, "flt", flt),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def pending(self, events, units=()):
		return demand.summarize(ENCARGO.requested_qty, events, list(units)).pending_supply_qty

	def buy(self, events, n, user, qty=1):
		"""confirm_purchase: decision on the residual recomputed under the Encargo lock, then one event."""
		decision, _previous = shopper.purchase_decision(
			{"status": "Open"}, events, user, f"REQ-{n}", qty, self.pending(events)
		)
		self.assertEqual(decision, "confirm")
		return events + [purchase(n, user, qty)]


class TestFourShoppers(AcceptanceCase):
	"""Cases 1-5 and §25: 1+1+1+1 by four Shoppers takes the queue 4->3->2->1->0."""

	def test_queue_goes_down_to_zero(self):
		events = []
		self.assertEqual(self.pending(events), 4)
		for n, user in enumerate(("a@x.cl", "b@x.cl", "c@x.cl", "d@x.cl"), start=1):
			events = self.buy(events, n, user)
			self.assertEqual(self.pending(events), 4 - n)
		with self.assertRaises(_Throw):
			self.buy(events, 5, "e@x.cl")

	def test_each_purchase_keeps_its_own_evidence(self):
		events = self.buy([], 1, "a@x.cl")
		events = self.buy(events, 2, "b@x.cl")
		self.assertEqual([(e.shopper_user, e.request_id) for e in events], [("a@x.cl", "REQ-1"), ("b@x.cl", "REQ-2")])

	def test_partial_purchase_consumes_only_its_qty(self):
		events = self.buy([], 1, "a@x.cl", qty=2)
		self.assertEqual(self.pending(events), 2)

	def test_last_unit_cannot_be_bought_twice(self):
		"""Case 7: the second Shopper re-reads the residual under the same lock and finds 0."""
		events = []
		for n in range(1, 4):
			events = self.buy(events, n, f"s{n}@x.cl")
		events = self.buy(events, 4, "a@x.cl")
		with self.assertRaises(_Throw):
			self.buy(events, 5, "b@x.cl")
		with self.assertRaises(_Throw):
			self.buy(events[:3], 6, "b@x.cl", qty=2)


class TestFourDirectReceptions(AcceptanceCase):
	"""Cases 9-12 and §25: four scans without Shopper purchase take the queue 4->3->2->1->0."""

	def test_queue_goes_down_to_zero_and_then_normal_stock(self):
		events, units = [], []
		for n in range(1, 5):
			pending = self.pending(events, units)
			self.assertEqual(pending, 5 - n)
			self.assertEqual(reception.pick_source(ENCARGO, events, {}, pending, CODE, [ITEM]), ("direct", None))
			event = direct(n)
			events, units = events + [event], units + [unit(event)]
		self.assertEqual(self.pending(events, units), 0)
		self.assertEqual(reception.pick_source(ENCARGO, events, {}, 0, CODE, [ITEM]), (None, None))
		self.assertFalse(reception.has_capacity(ENCARGO, len(units)))

	def test_unit_is_counted_once(self):
		"""Case 18: a unit satisfies its own event only; covered never exceeds requested."""
		events = [direct(n) for n in range(1, 5)]
		units = [unit(e) for e in events] + [unit(events[0])]
		totals = demand.summarize(ENCARGO.requested_qty, events, units)
		self.assertLessEqual(totals.covered_qty, ENCARGO.requested_qty)
		self.assertEqual(totals.pending_supply_qty, 0)


class TestOtherSources(AcceptanceCase):
	def test_stock_allocation_reduces_residual(self):
		"""Case 19."""
		stock = D(name="EV-S", idx=1, source_type=demand.STOCK, status=demand.RECEIVED, qty=1, released_qty=0)
		self.assertEqual(self.pending([stock]), 3)

	def test_released_purchase_keeps_history_and_arrives_as_stock(self):
		"""Case 20: the commitment is released, the demand is covered elsewhere, the late unit is normal stock."""
		released = purchase(1, "a@x.cl", status="RESOLVED_TO_STOCK", released_qty=1)
		self.assertEqual(self.pending([released]), 4)
		events = [released] + [direct(n) for n in range(2, 6)]
		units = [unit(e) for e in events[1:]]
		self.assertEqual(self.pending(events, units), 0)
		self.assertEqual(reception.pick_source(ENCARGO, events, {}, 0, CODE, [ITEM]), (None, None))
		self.assertEqual(events[0].shopper_user, "a@x.cl")

	def test_barcode_exception_holds_only_its_purchase(self):
		"""Case 21: one purchase waits for approval, the others are received; its quota stays taken."""
		waiting = purchase(1, "a@x.cl", purchase_barcode="OTRO", barcode_exception_status="PENDING_APPROVAL")
		ok = purchase(2, "b@x.cl")
		self.assertEqual(self.pending([waiting, ok]), 2)
		self.assertEqual(
			reception.pick_source(ENCARGO, [waiting, ok], {}, 2, CODE, [ITEM], {"EV-1", "EV-2"}), ("event", ok)
		)

	def test_repeated_reconciliation_is_stable(self):
		"""Case 24."""
		events = [purchase(1, "a@x.cl"), direct(2)]
		units = [unit(events[1])]
		self.assertEqual(
			demand.summarize(4, events, units), demand.summarize(4, list(events), list(units))
		)


if __name__ == "__main__":
	unittest.main()
