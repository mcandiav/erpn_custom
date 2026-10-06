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


def purchased(**values):
	row = {
		"name": "ENC-2026-00401",
		"status": "Open",
		"purchase_status": "PURCHASED",
		"reception_status": "PENDING",
		"purchase_barcode": QR,
		"source_type": "UNKNOWN_ITEM",
		"expected_item": None,
		"shopper_user": "shopper@fragallardo.com",
		"purchased_on": datetime(2026, 10, 1, 12, 0),
		"purchase_supplier": "MK Outlet",
		"purchase_price": 59.9,
		"purchase_product_image": "/private/files/p.jpg",
		"purchase_label_image": "/private/files/l.jpg",
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
			(reception, "flt", lambda v, *a, **k: round(float(v or 0), a[0] if a else 9)),
			(reception, "cint", lambda v: int(v or 0)),
			(reception, "now_datetime", lambda: NOW),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)


class TestRules(ReceptionCase):
	def test_role_gate(self):
		self.assertTrue(reception.is_receptor(["FRAreceptor"]))
		self.assertTrue(reception.is_receptor(["System Manager"]))
		self.assertFalse(reception.is_receptor(["ShopperFRA"]))
		self.assertFalse(reception.is_receptor(["ComercialFRA", "Sales User"]))

	def test_code_is_opaque(self):
		self.assertEqual(reception.clean_code(f"  {QR}\n"), QR)
		self.assertEqual(reception.clean_code("0198446906618"), "0198446906618")
		self.assertEqual(reception.clean_code(None), "")

	def test_exact_match_is_case_sensitive(self):
		rows = [D(name="A", purchase_barcode=QR), D(name="B", purchase_barcode=QR.lower())]
		self.assertEqual([r.name for r in reception.exact_matches(rows, QR)], ["A"])

	def test_oldest_pending_purchase_gets_the_unit(self):
		rows = [
			D(name="ENC-3", reception_status="PENDING", purchased_on=datetime(2026, 10, 3)),
			D(name="ENC-1", reception_status="RECEIVED", purchased_on=datetime(2026, 9, 1)),
			D(name="ENC-2", reception_status="PENDING", purchased_on=datetime(2026, 10, 2)),
		]
		self.assertEqual(reception.pick_candidate(rows).name, "ENC-2")
		self.assertIsNone(reception.pick_candidate([rows[1]]))
		self.assertIsNone(reception.pick_candidate([]))

	def test_receive_pending(self):
		self.assertEqual(reception.receive_decision(purchased(), "r1"), "receive")

	def test_receive_retry_same_user_is_idempotent(self):
		row = purchased(reception_status="RECEIVED", received_by="r1")
		self.assertEqual(reception.receive_decision(row, "r1"), "already_done")
		with self.assertRaises(_Throw):
			reception.receive_decision(row, "r2")

	def test_receive_requires_purchase(self):
		for values in ({"purchase_status": "PENDING"}, {"status": "Cancelled"}, {"reception_status": "RESOLVED_TO_ENC"}):
			with self.assertRaises(_Throw):
				reception.receive_decision(purchased(**values), "r1")
		with self.assertRaises(_Throw):
			reception.receive_decision(None, "r1")

	def test_resolve_requires_received(self):
		with self.assertRaises(_Throw):
			reception.resolve_decision(purchased(), "ITEM-1")
		self.assertEqual(reception.resolve_decision(purchased(reception_status="RECEIVED"), "ITEM-1"), "resolve")

	def test_no_silent_double_resolution(self):
		row = purchased(reception_status="RESOLVED_TO_ENC", resolved_item="ITEM-1")
		self.assertEqual(reception.resolve_decision(row, "ITEM-1"), "already_done")
		with self.assertRaises(_Throw):
			reception.resolve_decision(row, "ITEM-2")

	def test_valid_item(self):
		reception.require_valid_item({"name": "ITEM-1", "disabled": 0, "has_variants": 0})
		for item in (
			None,
			{"name": "ENCARGO-PENDIENTE"},
			{"name": "ITEM-1", "disabled": 1},
			{"name": "TEMPLATE", "has_variants": 1},
		):
			with self.assertRaises(_Throw):
				reception.require_valid_item(item)

	def test_known_item_mismatch_needs_confirmation(self):
		row = purchased(source_type="KNOWN_ITEM", expected_item="ITEM-1")
		reception.require_mismatch_confirmed(row, "ITEM-1", 0)
		reception.require_mismatch_confirmed(row, "ITEM-2", 1)
		with self.assertRaises(_Throw):
			reception.require_mismatch_confirmed(row, "ITEM-2", 0)

	def test_master_code_belongs_to_one_item(self):
		self.assertEqual(reception.barcode_link_decision(None, "ITEM-1"), "add")
		self.assertEqual(reception.barcode_link_decision("ITEM-1", "ITEM-1"), "already_done")
		with self.assertRaises(_Throw):
			reception.barcode_link_decision("ITEM-9", "ITEM-1")


class TestFlows(ReceptionCase):
	def setUp(self):
		super().setUp()
		log = patch.object(reception, "_log")
		self.log = log.start()
		self.addCleanup(log.stop)

	def test_shopper_is_rejected(self):
		with patch.object(self.frappe, "get_roles", lambda: ["ShopperFRA"]):
			with self.assertRaises(_Throw):
				reception.mark_received("ENC-2026-00401", QR)
		self.db.set_value.assert_not_called()

	def test_pilot_scan_detects_encargo_before_item(self):
		with patch.object(self.frappe, "get_all") as get_all:
			get_all.side_effect = [[purchased()], []]
			data = reception.find_candidates(f" {QR} ")
		self.assertEqual(data["match"], "encargo")
		self.assertEqual(data["encargo"]["name"], "ENC-2026-00401")
		self.assertEqual(get_all.call_args_list[0].kwargs["filters"]["purchase_barcode"], QR)
		self.assertIsNone(data["item"])

	def test_scan_without_encargo(self):
		with patch.object(self.frappe, "get_all") as get_all:
			get_all.side_effect = [[purchased(purchase_barcode=QR.lower())], []]
			data = reception.find_candidates(QR)
		self.assertEqual(data["match"], "none")
		self.assertIsNone(data["encargo"])

	def test_scan_when_every_encargo_already_received(self):
		with patch.object(self.frappe, "get_all") as get_all:
			get_all.side_effect = [[purchased(reception_status="RECEIVED", received_by="r1")], []]
			data = reception.find_candidates(QR)
		self.assertEqual(data["match"], "received")
		self.assertEqual(len(data["received"]), 1)

	def test_mark_received_records_receptor(self):
		self.db.get_value.return_value = purchased()
		reception.mark_received("ENC-2026-00401", QR)
		self.db.set_value.assert_called_once()
		values = self.db.set_value.call_args.args[2]
		self.assertEqual(values, {"reception_status": "RECEIVED", "received_on": NOW, "received_by": "r1@fragallardo.com"})
		self.log.assert_called_once_with("ENC-2026-00401", "RECEIVED", scanned_code=QR)

	def test_mark_received_retry_writes_nothing(self):
		self.db.get_value.return_value = purchased(reception_status="RECEIVED", received_by="r1@fragallardo.com")
		reception.mark_received("ENC-2026-00401", QR)
		self.db.set_value.assert_not_called()
		self.log.assert_not_called()

	def test_resolve_to_encargo(self):
		self.db.get_value.side_effect = [
			purchased(reception_status="RECEIVED"),
			{"name": "ITEM-1", "disabled": 0, "has_variants": 0},
		]
		reception.resolve_to_encargo("ENC-2026-00401", "ITEM-1")
		values = self.db.set_value.call_args.args[2]
		self.assertEqual(
			values, {"resolved_item": "ITEM-1", "resolved_by": "r1@fragallardo.com", "reception_status": "RESOLVED_TO_ENC"}
		)
		self.assertEqual(self.db.set_value.call_args.args[0], "Encargo")

	def test_resolve_links_code_when_confirmed(self):
		self.db.get_value.side_effect = [
			purchased(reception_status="RECEIVED"),
			{"name": "ITEM-1", "disabled": 0, "has_variants": 0},
		]
		with patch.object(reception, "_link_code") as link:
			reception.resolve_to_encargo("ENC-2026-00401", "ITEM-1", link_code=1)
		link.assert_called_once_with("ITEM-1", QR)

	def test_annul_purchase_keeps_evidence_and_reopens(self):
		self.db.get_value.side_effect = [
			purchased(reception_status="RECEIVED", received_by="r1@fragallardo.com"),
			{"name": "ITEM-WRONG", "disabled": 0, "has_variants": 0},
		]
		reception.annul_purchase("ENC-2026-00401", "ITEM-WRONG", notes="Color distinto")
		event = self.log.call_args
		self.assertEqual(event.args, ("ENC-2026-00401", "PURCHASE_ANNULLED"))
		self.assertEqual(event.kwargs["item"], "ITEM-WRONG")
		self.assertEqual(event.kwargs["purchase_barcode"], QR)
		self.assertEqual(event.kwargs["shopper_user"], "shopper@fragallardo.com")
		self.assertEqual(event.kwargs["purchase_product_image"], "/private/files/p.jpg")
		values = self.db.set_value.call_args.args[2]
		self.assertEqual(values["purchase_status"], "PENDING")
		self.assertEqual(values["reception_status"], "PENDING")
		self.assertIsNone(values["purchase_barcode"])

	def test_annul_requires_received(self):
		self.db.get_value.return_value = purchased()
		with self.assertRaises(_Throw):
			reception.annul_purchase("ENC-2026-00401", "ITEM-1")
		self.db.set_value.assert_not_called()


if __name__ == "__main__":
	unittest.main()
