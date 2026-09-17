import sys
import unittest
from unittest.mock import MagicMock, patch


class TestCourierRegistry(unittest.TestCase):
	def test_chilexpress_registered(self):
		from erpn_custom.chile.couriers.registry import registered_providers

		self.assertIn("chilexpress", registered_providers())

	def test_unknown_provider(self):
		from erpn_custom.chile.couriers.registry import get_courier_adapter

		with self.assertRaises(ValueError):
			get_courier_adapter("starken")


class TestChilexpressHelpers(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		# Offline import without a real Frappe install.
		sys.modules.setdefault("frappe", MagicMock())
		sys.modules.setdefault("frappe.utils", MagicMock())
		fake_utils = sys.modules["frappe.utils"]
		fake_utils.cint = int
		fake_utils.flt = float
		sys.modules.setdefault("requests", MagicMock())

	def test_norm_accents(self):
		from erpn_custom.chile.couriers.chilexpress import ChilexpressAdapter

		self.assertEqual(ChilexpressAdapter._norm("Ñuñoa"), "NUNOA")
		self.assertEqual(ChilexpressAdapter._norm("  Providencia "), "PROVIDENCIA")

	def test_incomplete_parcel_fails(self):
		from erpn_custom.chile.couriers.chilexpress import ChilexpressAdapter

		adapter = ChilexpressAdapter()
		row = MagicMock(weight=0, length=10, width=10, height=10, count=1)
		shipment = MagicMock(
			shipment_parcel=[row],
			value_of_goods=1000,
			description_of_content="test",
			pickup_address_name=None,
			delivery_address_name=None,
		)
		config = MagicMock(
			environment="Test",
			account_reference="18578680",
			provider="chilexpress",
		)
		with patch.object(adapter, "_api_key", return_value="k"), patch.object(
			adapter, "_endpoint", return_value="https://example.test/api"
		):
			result = adapter.validate_shipment(shipment, config)
		self.assertFalse(result["ok"])
		fields = [e.get("field") for e in result["errors"]]
		self.assertIn("weight", fields)
		self.assertTrue(any(e.get("section") == "origin" for e in result["errors"]))
