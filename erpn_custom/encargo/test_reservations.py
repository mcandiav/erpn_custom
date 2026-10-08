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

from erpn_custom.encargo import demand, reservations, supply  # noqa: E402

MATRIZ = "Matriz - FRAG"
RECEPCION = "Recepcion Encargos - FRAG"


class D(dict):
	__getattr__ = dict.get


def unit(name, sre, warehouse=RECEPCION, status="POSTED", destination="ENCARGO"):
	return D(name=name, status=status, destination=destination, warehouse=warehouse, stock_reservation_entry=sre)


def allocation(name, sre, warehouse=MATRIZ, released=0):
	return D(
		name=name,
		source_type=demand.STOCK,
		status=demand.RECEIVED,
		qty=1,
		released_qty=released,
		warehouse=warehouse,
		stock_reservation_entry=sre,
	)


def sre(name, warehouse, reserved=1, delivered=0, docstatus=1):
	return D(name=name, warehouse=warehouse, reserved_qty=reserved, delivered_qty=delivered, docstatus=docstatus)


LINE = D(idx=1, stock_qty=5, delivered_qty=0)


class ReservationCase(unittest.TestCase):
	def setUp(self):
		flt = lambda v, *a, **k: float(v or 0)  # noqa: E731
		for target, name, value in (
			(demand, "flt", flt),
			(demand.frappe, "_dict", D),
			(reservations, "flt", flt),
			(reservations, "_", lambda msg: msg),
			(supply, "flt", flt),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def codes(self, issues):
		return [i["code"] for i in issues]


class TestExpected(ReservationCase):
	def test_only_live_posted_units_and_active_allocations(self):
		units = [
			unit("U1", "S1"),
			unit("U2", "S2", status="RETURNED_TO_STOCK"),
			unit("U3", None, status="PENDING_COST"),
			unit("U4", "S4", destination="STOCK"),
		]
		events = [allocation("E1", "S5"), allocation("E2", "S6", released=1)]
		names = [e["name"] for e in reservations.expected_reservations(units, events)]
		self.assertEqual(names, ["U1", "E1"])


class TestReferenceProblems(ReservationCase):
	def test_pilot_ov_328_is_clean(self):
		units = [unit(f"U{i}", f"S{i}") for i in range(1, 5)]
		sres = [sre("S0", MATRIZ)] + [sre(f"S{i}", RECEPCION) for i in range(1, 5)]
		expected = reservations.expected_reservations(units, [])
		self.assertEqual(reservations.invalid_count(expected, sres), 0)
		self.assertEqual(reservations.diagnose_line(LINE, 5, expected, sres, []), [])

	def test_cancelled_or_missing_reservation(self):
		expected = reservations.expected_reservations([unit("U1", "S1"), unit("U2", None)], [])
		problems = reservations.reference_problems(expected, [sre("S1", RECEPCION, docstatus=2)])
		self.assertEqual([(c, e["name"]) for c, e, _s in problems], [("MISSING", "U1"), ("MISSING", "U2")])

	def test_reservation_left_in_matriz_after_move(self):
		expected = reservations.expected_reservations([unit("U1", "S1")], [])
		problems = reservations.reference_problems(expected, [sre("S1", MATRIZ)])
		self.assertEqual(problems[0][0], "WRONG_WAREHOUSE")

	def test_shared_reservation_counts_once(self):
		expected = reservations.expected_reservations([unit("U1", "S1"), unit("U2", "S1")], [])
		problems = reservations.reference_problems(expected, [sre("S1", RECEPCION)])
		self.assertEqual([(c, e["name"]) for c, e, _s in problems], [("DUPLICATE", "U2")])

	def test_allocation_reserved_in_its_warehouse(self):
		expected = reservations.expected_reservations([], [allocation("E1", "S1")])
		self.assertEqual(reservations.invalid_count(expected, [sre("S1", MATRIZ)]), 0)


class TestDiagnoseLine(ReservationCase):
	def test_line_totals(self):
		under = reservations.diagnose_line(LINE, 5, [], [sre("S0", MATRIZ, reserved=3)], [])
		self.assertEqual(self.codes(under), ["UNDER_RESERVED"])
		self.assertEqual(under[0]["qty"], 2)
		over = reservations.diagnose_line(LINE, 5, [], [sre("S0", MATRIZ, reserved=6)], [])
		self.assertEqual(self.codes(over), ["OVER_RESERVED"])

	def test_delivered_units_need_no_reservation(self):
		line = D(idx=1, stock_qty=5, delivered_qty=5)
		issues = reservations.diagnose_line(line, 5, [], [sre("S0", MATRIZ, reserved=5, delivered=5)], [])
		self.assertEqual(issues, [])

	def test_warehouse_reserved_beyond_stock(self):
		bins = [D(warehouse=MATRIZ, actual_qty=0, reserved_stock=1)]
		issues = reservations.diagnose_line(LINE, 1, [], [sre("S0", MATRIZ)], bins)
		self.assertEqual(self.codes(issues), ["OVER_STOCK"])
		self.assertFalse(issues[0]["repairable"])

	def test_only_own_references_are_repairable(self):
		expected = reservations.expected_reservations([unit("U1", None)], [])
		issues = reservations.diagnose_line(LINE, 4, expected, [sre("S0", MATRIZ, reserved=4)], [])
		self.assertEqual([(i["code"], i["repairable"]) for i in issues], [("MISSING", True)])


class TestCoverage(ReservationCase):
	def test_invalid_units_stay_sourced_but_not_covered(self):
		events = [D(name="E1", idx=1, source_type=demand.DIRECT, qty=1, status=demand.RECEIVED, released_qty=0)]
		units = [D(name="U1", supply_event="E1", status="POSTED", destination="ENCARGO")]
		t = demand.summarize(1, events, units, invalid=1)
		self.assertEqual((t.sourced_qty, t.pending_supply_qty, t.covered_qty, t.invalid_qty), (1, 0, 0, 1))

	def test_order_line_shows_invalid_reservation(self):
		enc = D(status="Open", source_type="KNOWN_ITEM", requested_qty=4, materialized_qty=0)
		totals = D(received_qty=4, legacy_qty=0, stock_qty=0, invalid_qty=1, waiting_qty=0,
			pending_receive_qty=0, exception_qty=0, pending_supply_qty=0)
		buckets = supply.encargo_buckets(enc, totals)
		self.assertEqual(buckets, [(supply.COVERED, 3), (supply.INVALID, 1)])
		line = supply.line_buckets(5, [buckets])
		self.assertEqual(line, [(supply.COVERED, 4), (supply.INVALID, 1)])
		self.assertEqual(supply.line_indicator(line), "orange")


if __name__ == "__main__":
	unittest.main()
