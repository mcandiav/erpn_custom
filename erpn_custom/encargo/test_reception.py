import sys
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.encargo import reception  # noqa: E402

NOW = datetime(2026, 10, 6, 10, 0)
QR = "https://qrgo.page.link/JsDVr"


class D(dict):
	__getattr__ = dict.get


def purchased(name="ENC-2026-00401", **values):
	row = {
		"name": name,
		"status": "Open",
		"purchase_status": "PURCHASED",
		"reception_status": "PENDING",
		"purchase_barcode": QR,
		"purchased_on": datetime(2026, 10, 1, 12, 0),
	}
	row.update(values)
	return D(row)


class ReceptionCase(unittest.TestCase):
	def setUp(self):
		# A private frappe per test: the shared mock belongs to whichever test module loaded first.
		self.frappe = MagicMock()
		self.frappe.throw = _throw
		self.frappe.get_roles = lambda: ["FRAreceptor"]
		self.frappe.session = D(user="r1@fragallardo.com")
		self.db = self.frappe.db
		for target, name, value in (
			(reception, "frappe", self.frappe),
			(reception, "_", lambda msg: msg),
			(reception, "cint", lambda v: int(v or 0)),
			(reception, "now_datetime", lambda: NOW),
			(reception, "getdate", lambda *a: date(2026, 10, 6)),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)


class TestRules(ReceptionCase):
	def test_receptor_gate(self):
		self.assertTrue(reception.is_receptor(["FRAreceptor"]))
		self.assertTrue(reception.is_receptor(["System Manager"]))
		self.assertFalse(reception.is_receptor(["ShopperFRA"]))
		self.assertFalse(reception.is_receptor(["ComercialFRA", "Sales User"]))

	def test_return_to_stock_gate(self):
		self.assertTrue(reception.can_return_to_stock(["ComercialFRA"]))
		self.assertTrue(reception.can_return_to_stock(["System Manager"]))
		self.assertFalse(reception.can_return_to_stock(["FRAreceptor"]))
		self.assertFalse(reception.can_return_to_stock(["ShopperFRA"]))

	def test_code_is_opaque(self):
		self.assertEqual(reception.clean_code(f"  {QR}\n"), QR)
		self.assertEqual(reception.clean_code("0198446906618"), "0198446906618")
		self.assertEqual(reception.clean_code(None), "")

	def test_exact_match_is_case_sensitive(self):
		rows = [D(name="A", purchase_barcode=QR), D(name="B", purchase_barcode=QR.lower())]
		self.assertEqual([r.name for r in reception.exact_matches(rows, QR)], ["A"])

	def test_oldest_purchase_first(self):
		rows = [
			D(name="ENC-3", purchased_on=datetime(2026, 10, 3)),
			D(name="ENC-1", purchased_on=datetime(2026, 9, 1)),
			D(name="ENC-2", purchased_on=datetime(2026, 10, 2)),
		]
		self.assertEqual([r.name for r in reception.oldest_first(rows)], ["ENC-1", "ENC-2", "ENC-3"])

	def test_receivable(self):
		self.assertTrue(reception.is_receivable(purchased()))
		for values in ({"purchase_status": "PENDING"}, {"status": "Cancelled"}, {"reception_status": "RECEIVED"}):
			self.assertFalse(reception.is_receivable(purchased(**values)))
		self.assertFalse(reception.is_receivable(None))

	def test_return_decision(self):
		self.assertEqual(reception.return_decision(purchased(reception_status="RECEIVED")), "return")
		self.assertEqual(reception.return_decision(purchased(reception_status="RESOLVED_TO_STOCK")), "already_done")
		for row in (None, purchased(), purchased(reception_status="RECEIVED", status="Cancelled")):
			with self.assertRaises(_Throw):
				reception.return_decision(row)


class TestReceiveScan(ReceptionCase):
	"""Encargos live in a dict; get_all, the row lock and set_value read and write it like the database."""

	def setUp(self):
		super().setUp()
		log = patch.object(reception, "_log")
		self.log = log.start()
		self.addCleanup(log.stop)
		card = patch.object(reception, "_card", lambda name: {"name": name})
		card.start()
		self.addCleanup(card.stop)
		self.store = {}
		self.frappe.get_all = self._get_all
		self.db.get_value = lambda doctype, name, *a, **k: D(self.store[name]) if name in self.store else None
		self.db.set_value = MagicMock(side_effect=lambda doctype, name, values, **k: self.store[name].update(values))

	def _get_all(self, doctype, filters=None, fields=None, **k):
		return [
			D(row)
			for row in self.store.values()
			if row["reception_status"] == filters["reception_status"]
			and row["purchase_barcode"].lower() == filters["purchase_barcode"].lower()
		]

	def add(self, name, day, **values):
		self.store[name] = purchased(name, purchased_on=datetime(2026, 10, day), **values)

	def test_pilot_scan_receives_the_encargo(self):
		self.add("ENC-2026-00401", 1)
		data = reception.receive_scan(f" {QR} ")
		self.assertEqual(data["match"], "encargo")
		self.assertEqual(data["encargo"]["name"], "ENC-2026-00401")
		self.assertEqual(data["pending_left"], 0)
		self.assertEqual(
			self.db.set_value.call_args.args[2],
			{"reception_status": "RECEIVED", "received_on": NOW, "received_by": "r1@fragallardo.com"},
		)
		self.log.assert_called_once_with("ENC-2026-00401", "RECEIVED", scanned_code=QR)

	def test_four_identical_units_three_encargos(self):
		self.add("ENC-C", 3)
		self.add("ENC-A", 1)
		self.add("ENC-B", 2)
		results = [reception.receive_scan(QR) for _ in range(4)]
		self.assertEqual([r.get("encargo", {}).get("name") for r in results[:3]], ["ENC-A", "ENC-B", "ENC-C"])
		self.assertEqual([r["pending_left"] for r in results[:3]], [2, 1, 0])
		self.assertEqual(results[3], {"match": "stock", "code": QR})
		self.assertEqual(self.db.set_value.call_count, 3)

	def test_scan_without_encargo_is_stock(self):
		self.add("ENC-2026-00401", 1, purchase_barcode=QR.lower())
		self.assertEqual(reception.receive_scan(QR), {"match": "stock", "code": QR})
		self.db.set_value.assert_not_called()
		self.log.assert_not_called()

	def test_unit_taken_by_another_receptor_goes_to_the_next(self):
		self.add("ENC-A", 1)
		self.add("ENC-B", 2)
		original = self.db.get_value

		def lock(doctype, name, *a, **k):
			if name == "ENC-A":
				self.store["ENC-A"]["reception_status"] = "RECEIVED"
			return original(doctype, name, *a, **k)

		self.db.get_value = lock
		data = reception.receive_scan(QR)
		self.assertEqual(data["encargo"]["name"], "ENC-B")
		self.assertEqual(self.db.set_value.call_count, 1)

	def test_empty_code_is_rejected(self):
		with self.assertRaises(_Throw):
			reception.receive_scan("   ")

	def test_non_receptor_is_rejected(self):
		self.add("ENC-2026-00401", 1)
		for roles in (["ShopperFRA"], ["ComercialFRA"]):
			with patch.object(self.frappe, "get_roles", lambda roles=roles: roles):
				with self.assertRaises(_Throw):
					reception.receive_scan(QR)
		self.db.set_value.assert_not_called()


class TestReturnToStock(ReceptionCase):
	def setUp(self):
		super().setUp()
		self.frappe.get_roles = lambda: ["ComercialFRA"]
		log = patch.object(reception, "_log")
		self.log = log.start()
		self.addCleanup(log.stop)

	def test_comercial_returns_received_unit(self):
		self.db.get_value.return_value = purchased(reception_status="RECEIVED")
		reception.return_to_stock("ENC-2026-00401", notes=" Color distinto ")
		self.assertEqual(
			self.db.set_value.call_args.args[2],
			{"reception_status": "RESOLVED_TO_STOCK", "resolved_by": "r1@fragallardo.com"},
		)
		self.log.assert_called_once_with("ENC-2026-00401", "RETURNED_TO_STOCK", scanned_code=QR, notes="Color distinto")

	def test_reason_is_required(self):
		self.db.get_value.return_value = purchased(reception_status="RECEIVED")
		with self.assertRaises(_Throw):
			reception.return_to_stock("ENC-2026-00401", notes="  ")
		self.db.set_value.assert_not_called()

	def test_requires_received(self):
		self.db.get_value.return_value = purchased()
		with self.assertRaises(_Throw):
			reception.return_to_stock("ENC-2026-00401", notes="Color distinto")
		self.db.set_value.assert_not_called()

	def test_repeat_writes_nothing(self):
		self.db.get_value.return_value = purchased(reception_status="RESOLVED_TO_STOCK")
		reception.return_to_stock("ENC-2026-00401", notes="Color distinto")
		self.db.set_value.assert_not_called()
		self.log.assert_not_called()

	def test_receptor_cannot_return(self):
		self.frappe.get_roles = lambda: ["FRAreceptor"]
		self.db.get_value.return_value = purchased(reception_status="RECEIVED")
		with self.assertRaises(_Throw):
			reception.return_to_stock("ENC-2026-00401", notes="Color distinto")
		self.db.set_value.assert_not_called()


if __name__ == "__main__":
	unittest.main()
