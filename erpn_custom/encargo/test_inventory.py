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

from erpn_custom.encargo import inventory  # noqa: E402

QR = "https://qrgo.page.link/JsDVr"


class InventoryCase(unittest.TestCase):
	def setUp(self):
		for name, value in (("_", lambda msg: msg), ("flt", lambda v, *a, **k: float(v or 0))):
			patcher = patch.object(inventory, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)


class TestItemCode(InventoryCase):
	def test_clean_codes_are_item_codes(self):
		self.assertTrue(inventory.usable_as_item_code("0198446906618"))
		self.assertTrue(inventory.usable_as_item_code("MK-BELT-01"))

	def test_qr_urls_and_dirty_codes_get_fra_series(self):
		for code in (QR, "A B", "", None, "X" * 41, "ABC/1", "Ñandú"):
			self.assertFalse(inventory.usable_as_item_code(code), code)

	def test_new_item_code_uses_series_for_qr(self):
		naming = MagicMock()
		naming.make_autoname.return_value = "FRA-00001"
		with patch.dict(sys.modules, {"frappe.model": MagicMock(), "frappe.model.naming": naming}):
			self.assertEqual(inventory.new_item_code(QR), "FRA-00001")
		naming.make_autoname.assert_called_once_with(inventory.ITEM_SERIES)


class TestRates(InventoryCase):
	def test_same_currency(self):
		self.assertEqual(inventory.choose_rate(0, 0, "CLP", "CLP"), (1.0, "SAME_CURRENCY"))

	def test_erpnext_rate_wins(self):
		self.assertEqual(inventory.choose_rate(950, 900, "USD", "CLP"), (950.0, "ERPNEXT"))

	def test_fallback_only_usd_clp(self):
		self.assertEqual(inventory.choose_rate(0, 900, "USD", "CLP"), (900.0, "FALLBACK"))
		self.assertEqual(inventory.choose_rate(0, 900, "EUR", "CLP"), (0.0, None))

	def test_no_rate_is_pending(self):
		self.assertEqual(inventory.choose_rate(0, 0, "USD", "CLP"), (0.0, None))

	def test_exchange_rate_uses_purchase_date(self):
		setup = MagicMock()
		setup.get_exchange_rate.return_value = 940
		with patch.dict(sys.modules, {"erpnext": MagicMock(), "erpnext.setup": MagicMock(), "erpnext.setup.utils": setup}), patch.object(
			inventory, "getdate", lambda d: "2026-10-01"
		), patch.object(inventory, "frappe") as frappe:
			frappe.db.get_single_value.return_value = 0
			self.assertEqual(inventory.exchange_rate("USD", "CLP", "2026-10-01 12:00"), (940.0, "ERPNEXT"))
		setup.get_exchange_rate.assert_called_once_with("USD", "CLP", "2026-10-01", "for_buying")

	def test_stock_rate_is_never_zero(self):
		self.assertEqual(inventory.choose_stock_rate(0, 15000, 12000), (15000.0, "VALUATION"))
		self.assertEqual(inventory.choose_stock_rate(None, 0, 12000), (12000.0, "LAST_INCOMING"))
		self.assertEqual(inventory.choose_stock_rate(14000, 15000, 12000), (14000.0, "VALUATION"))
		self.assertEqual(inventory.choose_stock_rate(0, 0, 0), (0.0, None))

	def test_pending_receive_qty(self):
		self.assertEqual(inventory.pending_receive_qty(3, 1), 2)
		self.assertEqual(inventory.pending_receive_qty(1, 2), 0)
		self.assertEqual(inventory.pending_receive_qty(None, None), 0)


class TestDecisions(InventoryCase):
	def test_known_item(self):
		self.assertEqual(inventory.known_item_decision("ITEM-1", "ITEM-1", True), "use")
		self.assertEqual(inventory.known_item_decision("ITEM-1", "ITEM-2", True), "mismatch")
		self.assertEqual(inventory.known_item_decision("ITEM-1", None, False), "adopt")
		self.assertEqual(inventory.known_item_decision("ITEM-1", None, True), "mismatch")

	def test_missing_classification(self):
		full = {"brand": "Michael Kors", "item_group": "Cinturones", "description": "Cinturón"}
		self.assertEqual(inventory.missing_classification(full, True), [])
		self.assertEqual(inventory.missing_classification(full, False), ["grupo de producto de último nivel"])
		self.assertEqual(
			inventory.missing_classification({"description": "  "}, False),
			["marca", "grupo de producto", "descripción"],
		)

	def test_clearing_account(self):
		ok = {"is_group": 0, "account_type": "", "company": "FRA"}
		self.assertIsNone(inventory.clearing_account_problem(ok, "FRA"))
		self.assertTrue(inventory.clearing_account_problem(None, "FRA"))
		self.assertTrue(inventory.clearing_account_problem({**ok, "is_group": 1}, "FRA"))
		self.assertTrue(inventory.clearing_account_problem({**ok, "account_type": "Stock"}, "FRA"))
		self.assertTrue(inventory.clearing_account_problem({**ok, "company": "Otra"}, "FRA"))


if __name__ == "__main__":
	unittest.main()
