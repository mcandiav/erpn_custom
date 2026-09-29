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
		row = {"status": "Open", "purchase_status": "PENDING"}
		self.assertEqual(shopper.purchase_decision(row, "s1@x.cl", "123"), "confirm")

	def test_retry_of_same_purchase_is_idempotent(self):
		row = {"status": "Open", "purchase_status": "PURCHASED", "shopper_user": "s1@x.cl", "purchase_barcode": "123"}
		self.assertEqual(shopper.purchase_decision(row, "s1@x.cl", "123"), "already_done")

	def test_second_shopper_cannot_overwrite(self):
		row = {"status": "Open", "purchase_status": "PURCHASED", "shopper_user": "s1@x.cl", "purchase_barcode": "123"}
		with self.assertRaises(_Throw):
			shopper.purchase_decision(row, "s2@x.cl", "123")
		with self.assertRaises(_Throw):
			shopper.purchase_decision(row, "s1@x.cl", "999")

	def test_cancelled_or_draft_not_purchasable(self):
		for status in ("Draft", "Cancelled", "Closed"):
			with self.assertRaises(_Throw):
				shopper.purchase_decision({"status": status, "purchase_status": "PENDING"}, "s1@x.cl", "1")

	def test_full_qty_confirmation(self):
		shopper.require_full_qty(1, 0)
		shopper.require_full_qty(2, 1)
		with self.assertRaises(_Throw):
			shopper.require_full_qty(2, 0)

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
		)
		row.get = lambda f, d=None: getattr(row, f, d) if f in ("custom_talla",) else None
		card = shopper._card(row)
		self.assertNotIn("customer", card)
		self.assertNotIn("sale_rate", card)
		self.assertNotIn("sales_order", card)
		self.assertEqual(card["talla"], "US 8 Â· EU 39 Â· CL 38")
		self.assertIn("shopper.reference_image?encargo=ENC-2026-00001", card["image"])
		self.assertEqual(card["variant"], "Talla: US 8 Â· EU 39 Â· CL 38")

	def test_list_fields_exclude_commercial_data(self):
		for field in ("customer", "sale_rate", "sales_order", "sales_person", "sales_order_item", "reference_url"):
			self.assertNotIn(field, shopper.LIST_FIELDS)
			self.assertNotIn(field, shopper.PURCHASE_FIELDS)

	def test_period_start(self):
		now = datetime(2026, 9, 28, 21, 30, 15)
		self.assertIsNone(shopper.period_start("all", now))
		self.assertEqual(shopper.period_start("7d", now), datetime(2026, 9, 21, 21, 30, 15))
		self.assertEqual(shopper.period_start("today", now), datetime(2026, 9, 28))
		self.assertEqual(shopper.period_start("otro", now), datetime(2026, 9, 28))

	def test_images_of_a_purchase_only_for_its_shopper(self):
		bought = {"status": "Open", "purchase_status": "PURCHASED", "shopper_user": "a@x.cl"}
		for kind in ("reference", "product", "label"):
			self.assertTrue(shopper.can_view_image(bought, "a@x.cl", kind))
			self.assertFalse(shopper.can_view_image(bought, "b@x.cl", kind))
		self.assertFalse(shopper.can_view_image(bought, "a@x.cl", "customer"))

	def test_pending_encargo_exposes_only_reference(self):
		pending = {"status": "Open", "purchase_status": "PENDING", "shopper_user": None}
		self.assertTrue(shopper.can_view_image(pending, "a@x.cl", "reference"))
		self.assertFalse(shopper.can_view_image(pending, "a@x.cl", "product"))
		self.assertFalse(shopper.can_view_image({**pending, "status": "Cancelled"}, "a@x.cl", "reference"))
		self.assertFalse(shopper.can_view_image(None, "a@x.cl", "reference"))


if __name__ == "__main__":
	unittest.main()
