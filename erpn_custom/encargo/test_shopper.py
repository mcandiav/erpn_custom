import base64
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.validate_and_sanitize_search_inputs = lambda f: f
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


_frappe.throw = _throw
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)
sys.modules.setdefault("frappe.utils.file_manager", MagicMock())

from erpn_custom.encargo import shopper  # noqa: E402

PNG = "data:image/png;base64," + base64.b64encode(b"img").decode()


class TestShopperRules(unittest.TestCase):
	def setUp(self):
		# Other test modules may have installed a different frappe mock first.
		for target, name, value in (
			(shopper.frappe, "throw", _throw),
			(shopper, "_", lambda msg: msg),
			(shopper, "flt", lambda v, *a, **k: float(v or 0)),
			(shopper, "cint", lambda v: int(v or 0)),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_currency_label_never_bare_dollar(self):
		self.assertEqual(shopper.currency_label("USD", "$"), "USD$")
		self.assertEqual(shopper.currency_label("EUR", "€"), "EUR€")
		self.assertEqual(shopper.currency_label("CHF", "CHF"), "CHF")
		self.assertEqual(shopper.currency_label(None, ""), "USD")

	def test_shopper_currency_defaults_to_usd(self):
		with patch.object(shopper.frappe.db, "get_value", return_value=None):
			self.assertEqual(shopper.shopper_currency("a@x.cl"), "USD")
		with patch.object(shopper.frappe.db, "get_value", return_value="EUR"):
			self.assertEqual(shopper.shopper_currency("b@x.cl"), "EUR")

	def test_totals_split_by_currency(self):
		rows = [
			{"purchase_currency": "USD", "purchase_total": 10},
			{"purchase_currency": "EUR", "purchase_total": 5.5},
			{"purchase_currency": "USD", "purchase_total": 2.25},
		]
		totals = shopper.totals_by_currency(rows, {"USD": "USD$", "EUR": "EUR€"})
		self.assertEqual(
			totals,
			[{"currency": "USD", "label": "USD$", "total": 12.25}, {"currency": "EUR", "label": "EUR€", "total": 5.5}],
		)
		self.assertEqual(shopper.totals_by_currency([], {}), [])

	def test_role_gate(self):
		self.assertTrue(shopper.is_shopper(["ShopperFRA", "Guest"]))
		self.assertFalse(shopper.is_shopper(["ComercialFRA", "Sales User"]))

	def test_all_four_evidences_required(self):
		self.assertEqual(shopper.missing_evidence("123", ("x", "jpg"), ("y", "jpg"), 49.99), [])
		missing = shopper.missing_evidence(" ", None, ("y", "jpg"), 0)
		self.assertEqual(missing, ["barcode", "foto del producto", "precio"])

	def test_decode_image(self):
		self.assertEqual(shopper.decode_image(PNG), (b"img", "png"))
		self.assertIsNone(shopper.decode_image("data:text/html;base64,PHA+"))
		self.assertIsNone(shopper.decode_image("data:image/jpeg;base64,***"))
		self.assertIsNone(shopper.decode_image(None))

	def test_pending_is_confirmed(self):
		row = {"status": "Open"}
		self.assertEqual(shopper.purchase_decision(row, [], "s1@x.cl", "REQ-00001", 2, 5), ("confirm", None))

	def test_partial_purchases_until_demand_is_sourced(self):
		row = {"status": "Open"}
		earlier = [{"request_id": "REQ-00001", "shopper_user": "s1@x.cl", "qty": 2}]
		self.assertEqual(shopper.purchase_decision(row, earlier, "s2@x.cl", "REQ-00002", 3, 3), ("confirm", None))
		with self.assertRaises(_Throw):
			shopper.purchase_decision(row, earlier, "s2@x.cl", "REQ-00002", 4, 3)
		with self.assertRaises(_Throw):
			shopper.purchase_decision(row, earlier, "s2@x.cl", "REQ-00003", 1, 0)

	def test_retry_of_same_purchase_is_idempotent(self):
		row = {"status": "Open"}
		previous = {"request_id": "REQ-00001", "shopper_user": "s1@x.cl"}
		self.assertEqual(
			shopper.purchase_decision(row, [previous], "s1@x.cl", "REQ-00001", 1, 0), ("already_done", previous)
		)

	def test_other_shopper_cannot_reuse_request(self):
		row = {"status": "Open"}
		previous = {"request_id": "REQ-00001", "shopper_user": "s1@x.cl"}
		with self.assertRaises(_Throw):
			shopper.purchase_decision(row, [previous], "s2@x.cl", "REQ-00001", 1, 4)

	def test_cancelled_or_draft_not_purchasable(self):
		for status in ("Draft", "Cancelled", "Closed"):
			with self.assertRaises(_Throw):
				shopper.purchase_decision({"status": status}, [], "s1@x.cl", None, 1, 1)

	def test_clean_qty_and_request_id(self):
		self.assertEqual(shopper.clean_qty("3"), 3)
		for bad in (0, -1, 1.5, None):
			with self.assertRaises(_Throw):
				shopper.clean_qty(bad)
		self.assertEqual(shopper.clean_request_id(" 1f2e3d4c-aaaa "), "1f2e3d4c-aaaa")
		self.assertIsNone(shopper.clean_request_id("x"))
		self.assertIsNone(shopper.clean_request_id("drop table;--"))

	def test_review_from_third_not_found(self):
		self.assertFalse(shopper.needs_review(2))
		self.assertTrue(shopper.needs_review(3))
		self.assertTrue(shopper.needs_review(4))

	def test_place_proposed_never_creates_supplier(self):
		with patch.object(shopper.frappe, "db") as db, patch.object(shopper.frappe, "get_doc"):
			self.assertEqual(shopper.resolve_place(None, "  Ross Dress  "), (None, "Ross Dress"))
			self.assertEqual(shopper.resolve_place("TODOS", "Ross"), (None, "Ross"))
			db.exists.assert_not_called()
			shopper.frappe.get_doc.assert_not_called()

	def test_place_master_supplier_wins(self):
		with patch.object(shopper.frappe, "db") as db:
			db.exists.return_value = True
			self.assertEqual(shopper.resolve_place("Macys", "otro"), ("Macys", None))
			db.exists.return_value = False
			with self.assertRaises(_Throw):
				shopper.resolve_place("Inventado", None)

	def test_place_required(self):
		with self.assertRaises(_Throw):
			shopper.resolve_place("TODOS", "  ")

	def test_list_card_hides_commercial_data(self):
		row = MagicMock()
		row.configure_mock(
			name="ENC-2026-00001",
			description="Bota",
			brand="Coach",
			supplier=None,
			custom_talla="US 8 Â· EU 39 Â· CL 38",
			custom_tamano=None,
			size=None,
			reference_image="/private/files/x.png",
			requested_qty=2,
			not_found_count=0,
			needs_commercial_review=0,
			reference_url="https://derp.at-once.cl/desk/sales-order/OV-2026-00003",
		)
		row.get = lambda f, d=None: getattr(row, f, d) if f in ("custom_talla",) else None
		card = shopper._card(row, "derp.at-once.cl")
		self.assertIsNone(card["reference_url"])
		self.assertIsNone(card["reference_text"])
		self.assertNotIn("customer", card)
		self.assertNotIn("sale_rate", card)
		self.assertNotIn("sales_order", card)
		self.assertEqual(card["talla"], "US 8 Â· EU 39 Â· CL 38")
		self.assertIn("shopper.reference_image?encargo=ENC-2026-00001", card["image"])
		self.assertEqual(card["variant"], "Talla: US 8 Â· EU 39 Â· CL 38")

	def test_list_fields_exclude_commercial_data(self):
		for field in ("customer", "sale_rate", "sales_order", "sales_person", "sales_order_item"):
			self.assertNotIn(field, shopper.LIST_FIELDS)
			self.assertNotIn(field, shopper.EVENT_FIELDS)

	def test_reference_link_keeps_store_links(self):
		host = "derp.at-once.cl"
		self.assertEqual(shopper.reference_link("https://www.zara.com/p1", host), ("https://www.zara.com/p1", None))
		self.assertEqual(shopper.reference_link(" www.zara.com/cl/p?x=1 ", host), ("https://www.zara.com/cl/p?x=1", None))
		self.assertEqual(shopper.reference_link("Ver foto en Instagram @tienda", host), (None, "Ver foto en Instagram @tienda"))
		self.assertEqual(shopper.reference_link("", host), (None, None))

	def test_reference_link_drops_erp_links(self):
		host = "derp.at-once.cl"
		for value in (
			"https://derp.at-once.cl/desk/sales-order/OV-2026-00003",
			"HTTPS://DERP.AT-ONCE.CL/app/encargo/ENC-1",
			"derp.at-once.cl/desk/sales-order/OV-2026-00003",
			"/desk/sales-order/OV-2026-00003",
		):
			self.assertEqual(shopper.reference_link(value, host), (None, None), value)

	def test_period_start(self):
		now = datetime(2026, 9, 28, 21, 30, 15)
		self.assertIsNone(shopper.period_start("all", now))
		self.assertEqual(shopper.period_start("7d", now), datetime(2026, 9, 21, 21, 30, 15))
		self.assertEqual(shopper.period_start("today", now), datetime(2026, 9, 28))
		self.assertEqual(shopper.period_start("otro", now), datetime(2026, 9, 28))

	def test_images_of_a_purchase_only_for_its_shopper(self):
		row = {"status": "Open", "pending_supply_qty": 0}
		event = {"shopper_user": "a@x.cl"}
		for kind in ("reference", "product", "label"):
			self.assertTrue(shopper.can_view_image(row, "a@x.cl", kind, event))
			self.assertFalse(shopper.can_view_image(row, "b@x.cl", kind, event))
		self.assertFalse(shopper.can_view_image(row, "a@x.cl", "customer", event))

	def test_pending_encargo_exposes_only_reference(self):
		pending = {"status": "Open", "pending_supply_qty": 2}
		self.assertTrue(shopper.can_view_image(pending, "a@x.cl", "reference"))
		self.assertFalse(shopper.can_view_image(pending, "a@x.cl", "product"))
		self.assertFalse(shopper.can_view_image({**pending, "pending_supply_qty": 0}, "a@x.cl", "reference"))
		self.assertFalse(shopper.can_view_image({**pending, "status": "Cancelled"}, "a@x.cl", "reference"))
		self.assertFalse(shopper.can_view_image(None, "a@x.cl", "reference"))


if __name__ == "__main__":
	unittest.main()
