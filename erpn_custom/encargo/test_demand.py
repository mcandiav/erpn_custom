import sys
import unittest
from datetime import datetime
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

from erpn_custom.encargo import demand, supply_actions  # noqa: E402
from erpn_custom.patches import v0_0_43_supply_events as migration  # noqa: E402


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


class D(dict):
	__getattr__ = dict.get


def event(name, source=demand.SHOPPER, qty=1, status=demand.COMMITTED, released=0, **values):
	return D(name=name, idx=values.pop("idx", 1), source_type=source, qty=qty, status=status, released_qty=released, **values)


def unit(event_name=None, status="POSTED", destination="ENCARGO", name=None):
	return D(name=name or f"U-{event_name}", supply_event=event_name, status=status, destination=destination)


class DemandCase(unittest.TestCase):
	def setUp(self):
		flt = lambda v, *a, **k: float(v or 0)  # noqa: E731
		for target, name, value in (
			(demand, "flt", flt),
			(demand.frappe, "_dict", D),
			(supply_actions, "flt", flt),
			(supply_actions, "_", lambda msg: msg),
			(supply_actions.frappe, "throw", _throw),
			(migration, "flt", flt),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)


class TestSummarize(DemandCase):
	def test_no_supply_is_all_pending(self):
		t = demand.summarize(5, [], [])
		self.assertEqual((t.sourced_qty, t.pending_supply_qty, t.covered_qty, t.pending_receive_qty), (0, 5, 0, 0))

	def test_partial_shopper_purchases_are_in_transit(self):
		t = demand.summarize(5, [event("E1", qty=2), event("E2", qty=1)], [])
		self.assertEqual((t.sourced_qty, t.pending_supply_qty, t.pending_receive_qty), (3, 2, 3))

	def test_arrival_moves_transit_to_covered(self):
		events = [event("E1", qty=2)]
		t = demand.summarize(2, events, [unit("E1"), unit("E1", status="RECEIVED", name="U2")])
		self.assertEqual((t.received_qty, t.waiting_qty, t.covered_qty, t.pending_receive_qty), (1, 1, 1, 0))
		self.assertEqual(t.event_status["E1"], demand.RECEIVED)
		self.assertEqual(t.event_received["E1"], 2)

	def test_ov_328_acceptance(self):
		"""4 direct receptions + 1 stock unit cover the 5 units; nothing left for the Shopper."""
		events = [event(f"D{i}", demand.DIRECT, status=demand.RECEIVED) for i in range(4)]
		events.append(event("S1", demand.STOCK, status=demand.RECEIVED))
		units = [unit(f"D{i}") for i in range(4)]
		t = demand.summarize(5, events, units)
		self.assertEqual((t.sourced_qty, t.pending_supply_qty, t.covered_qty, t.pending_receive_qty), (5, 0, 5, 0))

	def test_rejected_purchase_frees_the_quota(self):
		events = [event("E1", qty=2, status=demand.REJECTED, barcode_exception_status="REJECTED")]
		t = demand.summarize(2, events, [])
		self.assertEqual((t.sourced_qty, t.pending_supply_qty, t.pending_receive_qty), (0, 2, 0))

	def test_pending_barcode_still_occupies_quota(self):
		events = [event("E1", qty=2, barcode_exception_status="PENDING_APPROVAL")]
		t = demand.summarize(3, events, [])
		self.assertEqual((t.pending_supply_qty, t.exception_qty), (1, 2))

	def test_returned_unit_reopens_demand(self):
		events = [event("E1", qty=1, released=1)]
		t = demand.summarize(1, events, [unit("E1", status="RETURNED_TO_STOCK")])
		self.assertEqual((t.sourced_qty, t.pending_supply_qty, t.covered_qty), (0, 1, 0))
		self.assertEqual(t.event_status["E1"], demand.RESOLVED_TO_STOCK)

	def test_stock_destination_unit_is_not_coverage(self):
		t = demand.summarize(1, [], [unit(None, destination="STOCK")])
		self.assertEqual((t.covered_qty, t.pending_supply_qty), (0, 1))

	def test_unlinked_live_unit_still_sources_demand(self):
		t = demand.summarize(2, [], [unit(None)])
		self.assertEqual((t.sourced_qty, t.pending_supply_qty, t.covered_qty), (1, 1, 1))

	def test_migration_counts_as_covered_not_in_transit(self):
		t = demand.summarize(2, [event("M1", demand.MIGRATION, qty=2, status=demand.RECEIVED)], [])
		self.assertEqual((t.legacy_qty, t.covered_qty, t.pending_receive_qty, t.pending_supply_qty), (2, 2, 0, 0))

	def test_released_commitment_leaves_only_arrived(self):
		events = [event("E1", qty=3, released=2)]
		t = demand.summarize(3, events, [unit("E1")])
		self.assertEqual((t.sourced_qty, t.pending_supply_qty, t.pending_receive_qty), (1, 2, 0))

	def test_oversupply_never_goes_negative(self):
		t = demand.summarize(1, [event("E1", qty=1), event("S1", demand.STOCK, status=demand.RECEIVED)], [])
		self.assertEqual((t.pending_supply_qty, t.covered_qty), (0, 1))

	def test_requested_reduced_below_sourced(self):
		t = demand.summarize(1, [event("E1", qty=3)], [])
		self.assertEqual(t.pending_supply_qty, 0)

	def test_same_data_same_result(self):
		events = [event("E1", qty=2), event("S1", demand.STOCK, status=demand.RECEIVED)]
		units = [unit("E1")]
		self.assertEqual(demand.summarize(4, events, units), demand.summarize(4, events, units))


class TestDerivedMirrors(DemandCase):
	def test_purchase_status(self):
		self.assertEqual(demand.derived_purchase_status("PENDING", [event("E1")]), "PURCHASED")
		rejected = [event("E1", status=demand.REJECTED)]
		self.assertEqual(demand.derived_purchase_status("PURCHASED", rejected), "PENDING")
		self.assertEqual(demand.derived_purchase_status("PENDING", [event("S1", demand.STOCK, status=demand.RECEIVED)]), "PENDING")

	def test_barcode_status(self):
		pending = event("E1", barcode_exception_status="PENDING_APPROVAL")
		approved = event("E2", idx=2, barcode_exception_status="APPROVED")
		self.assertEqual(demand.derived_barcode_status("", [approved, pending]), "PENDING_APPROVAL")
		self.assertEqual(demand.derived_barcode_status("", [approved]), "APPROVED")
		self.assertEqual(demand.derived_barcode_status("MATCH", [event("S1", demand.STOCK)]), "MATCH")

	def test_fifo_by_creation_then_name(self):
		rows = [
			D(name="ENC-2", creation=datetime(2026, 10, 2)),
			D(name="ENC-9", creation=datetime(2026, 10, 1)),
			D(name="ENC-1", creation=datetime(2026, 10, 2)),
		]
		self.assertEqual([r.name for r in demand.oldest_first(rows)], ["ENC-9", "ENC-1", "ENC-2"])


class TestSupplyActions(DemandCase):
	def test_older_demand_blocks_fifo(self):
		rows = [
			D(name="ENC-2", creation=datetime(2026, 10, 2), pending_supply_qty=1),
			D(name="ENC-1", creation=datetime(2026, 10, 1), pending_supply_qty=2),
		]
		self.assertEqual(supply_actions.older_demand(rows, "ENC-2"), "ENC-1")
		self.assertIsNone(supply_actions.older_demand(rows, "ENC-1"))
		rows[1]["pending_supply_qty"] = 0
		self.assertIsNone(supply_actions.older_demand(rows, "ENC-2"))

	def test_release_amount(self):
		self.assertEqual(supply_actions.release_amount(event("E1", qty=3), 1), 2)
		self.assertEqual(supply_actions.release_amount(event("S1", demand.STOCK, status=demand.RECEIVED), 0), 1)
		self.assertEqual(supply_actions.release_amount(event("D1", demand.DIRECT, status=demand.RECEIVED), 1), 0)
		self.assertEqual(supply_actions.release_amount(event("E1", status=demand.REJECTED), 0), 0)

	def test_regularization_candidates(self):
		enc = D(expected_item="191267529486", creation="2026-10-06 09:00:00")
		units = [
			D(name="RCU-3", item="191267529486", received_on="2026-10-06 12:00:00"),
			D(name="RCU-1", item="191267529486", received_on="2026-10-06 10:00:00"),
			D(name="RCU-0", item="191267529486", received_on="2026-10-05 10:00:00"),
			D(name="RCU-2", item="OTRO", received_on="2026-10-06 11:00:00"),
		]
		chosen = supply_actions.regularization_candidates(units, enc, 4)
		self.assertEqual([u.name for u in chosen], ["RCU-1", "RCU-3"])
		self.assertEqual([u.name for u in supply_actions.regularization_candidates(units, enc, 1)], ["RCU-1"])
		self.assertEqual(supply_actions.regularization_candidates(units, enc, 0), [])

	def test_whole_qty_and_reason(self):
		self.assertEqual(supply_actions.whole_qty("2"), 2)
		for bad in (0, 1.5, None, -3):
			with self.assertRaises(_Throw):
				supply_actions.whole_qty(bad)
		self.assertEqual(supply_actions.clean_reason("  sin stock en tienda "), "sin stock en tienda")


class TestMigration(DemandCase):
	def legacy(self, **values):
		row = D(requested_qty=2, reception_status="PENDING", barcode_exception_status="")
		row.update(values)
		return row

	def test_purchase_in_transit(self):
		self.assertEqual(migration.legacy_event(self.legacy(), []), (demand.SHOPPER, demand.COMMITTED, 0))

	def test_rejected_purchase(self):
		row = self.legacy(barcode_exception_status="REJECTED")
		self.assertEqual(migration.legacy_event(row, [unit(None)]), (demand.SHOPPER, demand.REJECTED, 0))

	def test_pre_018_reception_without_units(self):
		self.assertEqual(
			migration.legacy_event(self.legacy(reception_status="RESOLVED_TO_ENC"), []),
			(demand.MIGRATION, demand.RECEIVED, 0),
		)
		self.assertEqual(
			migration.legacy_event(self.legacy(reception_status="RESOLVED_TO_STOCK"), []),
			(demand.MIGRATION, demand.RESOLVED_TO_STOCK, 0),
		)

	def test_returned_units_are_released(self):
		units = [unit(None, name="U1"), unit(None, status="RETURNED_TO_STOCK", name="U2"), unit(None, destination="STOCK", name="U3")]
		self.assertEqual(
			migration.legacy_event(self.legacy(requested_qty=2, reception_status="RECEIVED"), units),
			(demand.SHOPPER, demand.COMMITTED, 2),
		)


if __name__ == "__main__":
	unittest.main()
