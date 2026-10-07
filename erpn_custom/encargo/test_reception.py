import json
import os
import sys
import unittest
from contextlib import nullcontext
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

from erpn_custom.encargo import inventory, materialization, reception  # noqa: E402

NOW = datetime(2026, 10, 6, 10, 0)
QR = "https://qrgo.page.link/JsDVr"
SCAN_ID = "0b7c6f0e-3c1a-4c55-9d7a-1f2e3d4c5b6a"


class D(dict):
	__getattr__ = dict.get

	def __setattr__(self, key, value):
		self[key] = value


def purchased(name="ENC-2026-00401", **values):
	row = {
		"name": name,
		"status": "Open",
		"purchase_status": "PURCHASED",
		"reception_status": "PENDING",
		"purchase_barcode": QR,
		"purchased_on": datetime(2026, 10, 1, 12, 0),
		"purchase_price": 80,
		"purchase_currency": "USD",
		"requested_qty": 1,
		"received_qty": 0,
		"source_type": "UNKNOWN_ITEM",
		"sales_order": "SO-1",
		"sales_order_item": "SOI-1",
		"customer": "Cliente",
	}
	row.update(values)
	return D(row)


def unit(**values):
	row = D(
		name="RCU-2026-00001",
		scanned_code=QR,
		status=reception.PENDING_CLASSIFICATION,
		destination=reception.STOCK,
		received_on=NOW,
		received_by="r1@fragallardo.com",
	)
	row.update(values)
	return row


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
			(reception, "flt", lambda v, *a, **k: float(v or 0)),
			(reception, "now_datetime", lambda: NOW),
			(reception, "getdate", lambda *a: date(2026, 10, 6)),
			(reception, "strip_html", lambda v: v),
			(reception, "administrator_context", nullcontext),
			(inventory, "_", lambda msg: msg),
			(inventory, "flt", lambda v, *a, **k: float(v or 0)),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)


class TestRules(ReceptionCase):
	def test_role_gates(self):
		self.assertTrue(reception.is_receptor(["FRAreceptor"]))
		self.assertTrue(reception.is_receptor(["System Manager"]))
		self.assertFalse(reception.is_receptor(["ShopperFRA"]))
		self.assertFalse(reception.is_receptor(["ComercialFRA"]))
		self.assertTrue(reception.is_commercial(["ComercialFRA"]))
		self.assertFalse(reception.is_commercial(["FRAreceptor"]))
		self.assertTrue(reception.is_admin(["System Manager"]))
		self.assertFalse(reception.is_admin(["ComercialFRA"]))

	def test_code_is_opaque(self):
		self.assertEqual(reception.clean_code(f"  {QR}\n"), QR)
		self.assertEqual(reception.clean_code(None), "")

	def test_scan_event_id(self):
		self.assertEqual(reception.clean_scan_event_id(f" {SCAN_ID} "), SCAN_ID)
		for value in (None, "", "short", "x" * 65, "abc def ghij", "<script>1234"):
			with self.assertRaises(_Throw):
				reception.clean_scan_event_id(value)

	def test_migration_ids(self):
		self.assertEqual(reception.migration_scan_event_id("ENC-1"), "MIG-ENC-1")
		self.assertEqual(reception.migration_destination("RESOLVED_TO_STOCK"), reception.STOCK)
		self.assertEqual(reception.migration_destination("RECEIVED"), reception.ENCARGO)

	def test_screen(self):
		self.assertEqual(reception.screen("POSTED", "ENCARGO", True), ("APARTAR", "encargo"))
		self.assertEqual(reception.screen("POSTED", "STOCK", False), ("STOCK NORMAL", "stock"))
		self.assertEqual(reception.screen("PENDING_CLASSIFICATION", "ENCARGO", True)[0], "APARTAR - REQUIERE CLASIFICACION")
		self.assertEqual(reception.screen("PENDING_CLASSIFICATION", "STOCK", False)[0], "STOCK NORMAL - REQUIERE CLASIFICACION")
		self.assertEqual(reception.screen("PENDING_BARCODE_APPROVAL", "ENCARGO", True)[0], "APARTAR - REQUIERE COMERCIAL")
		for status in ("PENDING_COST", "PENDING_CONFIGURATION"):
			self.assertEqual(reception.screen(status, "ENCARGO", True), ("RECIBIDO - PENDIENTE DE VALORIZACION", "warning"))

	def test_screen_when_order_link_failed(self):
		self.assertEqual(
			reception.screen("POSTED", "ENCARGO", True, "ERROR", "ENC-2026-00401"),
			("APARTAR - ENC-2026-00401 - PENDIENTE DE VINCULAR A OV", "warning"),
		)
		for status in ("PENDING", "MATERIALIZED", None):
			self.assertEqual(reception.screen("POSTED", "ENCARGO", True, status, "ENC-1"), ("APARTAR", "encargo"))

	def test_link_queue_holds_only_retryable_set_aside_units(self):
		view = reception.COMMERCIAL_VIEWS["vincular"]
		self.assertEqual((view["status"], view["destination"]), ("POSTED", "ENCARGO"))
		self.assertEqual(view["materialization_status"], ("in", ["PENDING", "ERROR"]))

	def test_exact_match_is_case_sensitive(self):
		rows = [D(name="A", purchase_barcode=QR), D(name="B", purchase_barcode=QR.lower())]
		self.assertEqual([r.name for r in reception.exact_matches(rows, QR)], ["A"])

	def test_encargo_matches_known_item_by_barcode(self):
		known = D(purchase_barcode="otro", source_type="KNOWN_ITEM", expected_item="ITEM-1")
		self.assertTrue(reception.encargo_matches(known, QR, ["ITEM-1"]))
		self.assertFalse(reception.encargo_matches(known, QR, ["ITEM-2"]))
		self.assertTrue(reception.encargo_matches(D(purchase_barcode=QR), QR, []))

	def test_oldest_purchase_first(self):
		rows = [
			D(name="ENC-3", purchased_on=datetime(2026, 10, 3)),
			D(name="ENC-1", purchased_on=datetime(2026, 9, 1)),
			D(name="ENC-2", purchased_on=datetime(2026, 10, 2)),
		]
		self.assertEqual([r.name for r in reception.oldest_first(rows)], ["ENC-1", "ENC-2", "ENC-3"])

	def test_receivable_and_capacity(self):
		self.assertTrue(reception.is_receivable(purchased()))
		for values in ({"purchase_status": "PENDING"}, {"status": "Cancelled"}, {"reception_status": "RECEIVED"}):
			self.assertFalse(reception.is_receivable(purchased(**values)))
		self.assertTrue(reception.has_capacity(purchased(requested_qty=3), 2))
		self.assertFalse(reception.has_capacity(purchased(requested_qty=3), 3))

	def test_received_values_count_units(self):
		first = reception.received_values(purchased(requested_qty=2), NOW, "r1")
		self.assertEqual((first["received_qty"], first["pending_receive_qty"], first["reception_status"]), (1, 1, "PENDING"))
		last = reception.received_values(purchased(requested_qty=2, received_qty=1), NOW, "r1")
		self.assertEqual((last["received_qty"], last["pending_receive_qty"], last["reception_status"]), (2, 0, "RECEIVED"))

	def test_released_values(self):
		values = reception.released_values(purchased(requested_qty=2, received_qty=2), "c1")
		self.assertEqual(values["received_qty"], 1)
		self.assertEqual(values["pending_receive_qty"], 1)
		self.assertEqual(values["reception_status"], "RESOLVED_TO_STOCK")

	def test_return_decision(self):
		self.assertEqual(reception.return_decision(D(status="POSTED", destination="ENCARGO")), "return")
		self.assertEqual(reception.return_decision(D(status="RETURNED_TO_STOCK")), "already_done")
		for row in (None, D(status="POSTED", destination="STOCK"), D(status="PENDING_COST", destination="ENCARGO")):
			with self.assertRaises(_Throw):
				reception.return_decision(row)


class TestAdvance(ReceptionCase):
	"""_advance with the ERPNext side mocked: each pending state and the full posting."""

	def setUp(self):
		super().setUp()
		self.enc = purchased(resolved_item="ITEM-1")
		self.inv = {}
		for name, value in (
			("items_for_barcode", lambda code: ["ITEM-1"]),
			("clearing_account", lambda: "Compras Shopper por regularizar - FRAG"),
			("reception_company", lambda: "Fragallardo"),
			("exchange_rate", lambda *a: (950.0, "ERPNEXT")),
			("stock_rate", lambda *a: (12000.0, "VALUATION")),
			("make_receipt", MagicMock(return_value="MAT-STE-1")),
			("reserve_unit", MagicMock(return_value=("SRE-1", None))),
		):
			patcher = patch.object(inventory, name, value)
			self.inv[name] = patcher.start()
			self.addCleanup(patcher.stop)
		for name, value in (("_lock", lambda name: self.enc), ("_log", MagicMock())):
			patcher = patch.object(reception, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)
		patcher = patch.object(materialization, "materialize")
		self.materialize = patcher.start()
		self.addCleanup(patcher.stop)
		self.frappe.get_cached_value = lambda *a: "CLP"

	def encargo_unit(self):
		u = unit()
		reception._link_encargo(u, self.enc)
		return u

	def test_shopper_unit_is_posted_and_counted(self):
		u = self.encargo_unit()
		reception._advance(u)
		self.assertEqual(u.status, reception.POSTED)
		self.assertEqual(u.item, "ITEM-1")
		self.assertEqual(u.warehouse, inventory.ENCARGO_WAREHOUSE)
		self.assertEqual(u.incoming_rate, 80 * 950.0)
		self.assertEqual(u.stock_entry, "MAT-STE-1")
		values = self.db.set_value.call_args.args[2]
		self.assertEqual((values["received_qty"], values["reception_status"]), (1, "RECEIVED"))
		self.inv["reserve_unit"].assert_not_called()
		reception._log.assert_called_once_with(self.enc.name, "RECEIVED", "r1@fragallardo.com", scanned_code=QR)

	def test_encargo_pendiente_unit_is_materialized_after_the_receipt(self):
		u = self.encargo_unit()
		reception._advance(u)
		self.assertEqual((u.status, u.materialization_status), (reception.POSTED, materialization.PENDING))
		self.materialize.assert_called_once_with(u)

	def test_known_item_is_not_materialized(self):
		self.enc = purchased(source_type="KNOWN_ITEM", expected_item="ITEM-1")
		u = self.encargo_unit()
		reception._advance(u, ["ITEM-1"])
		self.materialize.assert_not_called()
		self.assertIsNone(u.materialization_status)

	def test_regularized_unit_logs_who_regularized(self):
		u = self.encargo_unit()
		u.update(is_migration=1, owner="admin@fragallardo.com")
		reception._advance(u)
		self.assertEqual(u.status, reception.POSTED)
		reception._log.assert_called_once_with(
			self.enc.name, "RECEIVED", "admin@fragallardo.com", scanned_code=QR, notes="Regularización RCU-2026-00001"
		)

	def test_known_item_unit_is_reserved(self):
		self.enc = purchased(source_type="KNOWN_ITEM", expected_item="ITEM-1")
		u = self.encargo_unit()
		reception._advance(u, ["ITEM-1"])
		self.assertEqual(u.stock_reservation_entry, "SRE-1")
		self.inv["reserve_unit"].assert_called_once_with("SO-1", "SOI-1", "ITEM-1", inventory.ENCARGO_WAREHOUSE)

	def test_known_item_with_other_barcode_needs_commercial(self):
		self.enc = purchased(source_type="KNOWN_ITEM", expected_item="ITEM-1")
		u = self.encargo_unit()
		reception._advance(u, ["ITEM-9"])
		self.assertEqual(u.status, reception.PENDING_BARCODE_APPROVAL)
		self.inv["make_receipt"].assert_not_called()

	def test_missing_account_is_pending_configuration(self):
		with patch.object(inventory, "clearing_account", lambda: None):
			u = self.encargo_unit()
			reception._advance(u)
		self.assertEqual(u.status, reception.PENDING_CONFIGURATION)
		self.inv["make_receipt"].assert_not_called()
		self.db.set_value.assert_not_called()

	def test_missing_rate_is_pending_cost(self):
		with patch.object(inventory, "exchange_rate", lambda *a: (0.0, None)):
			u = self.encargo_unit()
			reception._advance(u)
		self.assertEqual(u.status, reception.PENDING_COST)
		self.inv["make_receipt"].assert_not_called()

	def test_receipt_error_is_pending_cost(self):
		self.inv["make_receipt"].side_effect = Exception("Cuenta inválida")
		u = self.encargo_unit()
		reception._advance(u)
		self.assertEqual(u.status, reception.PENDING_COST)
		self.assertIn("Cuenta inválida", u.message)
		self.db.rollback.assert_called_once_with(save_point="reception_receipt")
		self.db.set_value.assert_not_called()

	def test_unknown_code_without_encargo_needs_classification(self):
		u = unit()
		reception._advance(u, [])
		self.assertEqual(u.status, reception.PENDING_CLASSIFICATION)

	def test_known_code_without_encargo_goes_to_stock_at_cost(self):
		u = unit()
		reception._advance(u, ["ITEM-5"])
		self.assertEqual((u.status, u.item, u.warehouse, u.incoming_rate), (reception.POSTED, "ITEM-5", inventory.STOCK_WAREHOUSE, 12000.0))
		self.db.set_value.assert_not_called()


class TestEndpoints(ReceptionCase):
	def test_repeated_read_is_a_noop(self):
		self.db.get_value = MagicMock(return_value="RCU-1")
		with patch.object(reception, "unit_result", lambda name, duplicate=False: {"unit": name, "duplicate": duplicate}):
			self.assertEqual(reception.receive_scan(QR, SCAN_ID), {"unit": "RCU-1", "duplicate": True})
		self.frappe.get_doc.assert_not_called()

	def test_read_without_id_is_rejected(self):
		with self.assertRaises(_Throw):
			reception.receive_scan(QR)

	def test_receptor_gate(self):
		for roles in (["ShopperFRA"], ["ComercialFRA"]):
			self.frappe.get_roles = lambda roles=roles: roles
			with self.assertRaises(_Throw):
				reception.receive_scan(QR, SCAN_ID)

	def test_return_requires_commercial_and_reason(self):
		with self.assertRaises(_Throw):
			reception.return_unit("RCU-1", "Color distinto")
		self.frappe.get_roles = lambda: ["ComercialFRA"]
		with self.assertRaises(_Throw):
			reception.return_unit("RCU-1", "  ")

	def test_return_moves_unit_and_releases_encargo(self):
		self.frappe.get_roles = lambda: ["ComercialFRA"]
		self.db.get_value = MagicMock(return_value=D(name="RCU-1", status="POSTED", destination="ENCARGO"))
		doc = unit(name="RCU-1", status="POSTED", destination="ENCARGO", encargo="ENC-1", item="ITEM-1",
			warehouse=inventory.ENCARGO_WAREHOUSE, stock_reservation_entry="SRE-1")
		doc.save = MagicMock()
		self.frappe.get_doc = lambda *a: doc
		with patch.object(inventory, "cancel_reservation") as cancel, patch.object(
			inventory, "make_transfer", return_value="MAT-STE-2"
		) as transfer, patch.object(inventory, "reception_company", lambda: "Fragallardo"), patch.object(
			reception, "_lock", lambda name: purchased("ENC-1", requested_qty=1, received_qty=1)
		), patch.object(reception, "_log") as log, patch.object(reception, "unit_result", lambda name: name):
			reception.return_unit("RCU-1", " Color distinto ")
		cancel.assert_called_once_with("SRE-1")
		self.assertEqual(transfer.call_args.args[2:4], (inventory.ENCARGO_WAREHOUSE, inventory.STOCK_WAREHOUSE))
		self.assertEqual((doc.status, doc.warehouse, doc.return_reason), ("RETURNED_TO_STOCK", inventory.STOCK_WAREHOUSE, "Color distinto"))
		self.assertEqual(self.db.set_value.call_args.args[2]["received_qty"], 0)
		log.assert_called_once()

	def test_retry_link_runs_the_same_service(self):
		self.frappe.get_roles = lambda: ["ComercialFRA"]
		self.frappe.session = D(user="c1@fragallardo.com")
		self.db.get_value = MagicMock(return_value=D(status="POSTED", destination="ENCARGO", materialization_status="ERROR"))
		doc = unit(name="RCU-1", status="POSTED", destination="ENCARGO", encargo="ENC-1")
		doc.save = MagicMock()
		self.frappe.get_doc = lambda *a: doc
		with patch.object(materialization, "materialize") as materialize, patch.object(
			reception, "unit_result", lambda name: name
		):
			self.assertEqual(reception.retry_materialization("RCU-1"), "RCU-1")
		materialize.assert_called_once_with(doc, "c1@fragallardo.com")
		doc.save.assert_called_once_with(ignore_permissions=True)

	def test_retry_link_rejects_units_not_waiting(self):
		self.frappe.get_roles = lambda: ["ComercialFRA"]
		for row in (
			None,
			D(status="POSTED", destination="ENCARGO", materialization_status="MATERIALIZED"),
			D(status="POSTED", destination="STOCK", materialization_status=None),
			D(status="PENDING_COST", destination="ENCARGO", materialization_status="PENDING"),
		):
			self.db.get_value = MagicMock(return_value=row)
			with self.subTest(row=row), self.assertRaises(_Throw):
				reception.retry_materialization("RCU-1")
		self.frappe.get_doc.assert_not_called()

	def test_regularize_is_admin_only(self):
		self.frappe.get_roles = lambda: ["ComercialFRA"]
		with self.assertRaises(_Throw):
			reception.regularize_previous_receptions()


APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _roles_in(*parts):
	with open(os.path.join(APP_DIR, *parts), encoding="utf-8") as f:
		return {row["role"] for row in json.load(f)["roles"]}


class TestPermissions(ReceptionCase):
	ENDPOINTS = {
		"receive_scan": lambda: reception.receive_scan(QR, SCAN_ID),
		"list_reception": lambda: reception.list_reception(),
		"list_units": lambda: reception.list_units(),
		"resolve_unit": lambda: reception.resolve_unit("RCU-1"),
		"return_unit": lambda: reception.return_unit("RCU-1", "Motivo"),
		"retry_materialization": lambda: reception.retry_materialization("RCU-1"),
		"regularize": lambda: reception.regularize_previous_receptions(),
	}
	DENIED = {
		"FRAreceptor": ("list_units", "resolve_unit", "return_unit", "retry_materialization", "regularize"),
		"ComercialFRA": ("receive_scan", "list_reception", "regularize"),
		"ShopperFRA": tuple(ENDPOINTS),
	}

	def test_each_role_is_denied_outside_its_job(self):
		for role, endpoints in self.DENIED.items():
			self.frappe.get_roles = lambda role=role: [role]
			for endpoint in endpoints:
				with self.subTest(role=role, endpoint=endpoint), self.assertRaises(_Throw):
					self.ENDPOINTS[endpoint]()
		self.frappe.get_doc.assert_not_called()
		self.db.set_value.assert_not_called()

	def test_pages_and_icons_follow_the_role_split(self):
		receptor = {"FRAreceptor", "System Manager"}
		commercial = {"ComercialFRA", "System Manager"}
		self.assertEqual(_roles_in("encargo", "page", "recepcion_chile", "recepcion_chile.json"), receptor)
		self.assertEqual(_roles_in("encargo", "page", "recepcion_comercial", "recepcion_comercial.json"), commercial)
		self.assertEqual(_roles_in("desktop_icon", "recepción_chile.json"), receptor)
		self.assertEqual(_roles_in("desktop_icon", "recepción_comercial.json"), commercial)

	def test_commercial_icon_opens_the_commercial_page(self):
		with open(os.path.join(APP_DIR, "desktop_icon", "recepción_comercial.json"), encoding="utf-8") as f:
			icon = json.load(f)
		with open(os.path.join(APP_DIR, "workspace_sidebar", "recepción_comercial.json"), encoding="utf-8") as f:
			sidebar = json.load(f)
		self.assertEqual((icon["parent_icon"], icon["link_type"], icon["link_to"]), ("MCV Chile", "Workspace Sidebar", sidebar["name"]))
		self.assertIn(("Page", "recepcion-comercial"), [(i["link_type"], i["link_to"]) for i in sidebar["items"]])


if __name__ == "__main__":
	unittest.main()
