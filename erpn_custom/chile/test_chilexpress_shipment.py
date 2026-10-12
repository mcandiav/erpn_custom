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

	def test_provider_messages_from_rejected_details(self):
		from erpn_custom.chile.couriers.chilexpress import ChilexpressAdapter

		payload = {
			"header": {"certificateNumber": 0},
			"detail": [
				{"transportOrderNumber": 0, "statusCode": -1, "statusDescription": "Numero de calle invalido"},
				{"statusCode": 0, "statusDescription": "OK"},
				{"errors": ["Telefono de contacto requerido", "Telefono de contacto requerido"]},
				{"labelData": "x" * 500},
			],
		}
		self.assertEqual(
			ChilexpressAdapter._provider_messages(payload),
			["[-1] Numero de calle invalido", "Telefono de contacto requerido"],
		)
		self.assertEqual(ChilexpressAdapter._provider_messages(None), [])
		self.assertEqual(ChilexpressAdapter._provider_messages("texto"), [])

	def test_request_surfaces_detail_reasons(self):
		import json

		from erpn_custom.chile.couriers import chilexpress as module
		from erpn_custom.chile.couriers.chilexpress import ChilexpressAdapter

		body = {
			"statusCode": -1,
			"statusDescription": "Ninguno de los detalles de generación de OT fue exitoso",
			"data": {"detail": [{"statusCode": 99, "statusDescription": "Contacto sin telefono"}]},
		}
		response = MagicMock(status_code=200, text=json.dumps(body))
		response.json.return_value = body
		thrown = []

		def fake_throw(msg, *args, **kwargs):
			thrown.append(msg)
			raise RuntimeError(msg)

		adapter = ChilexpressAdapter()
		with patch.object(adapter, "_api_key", return_value="k"), patch.object(
			adapter, "_endpoint", return_value="https://example.test/api"
		), patch.object(module.requests, "post", return_value=response), patch.object(
			module.frappe, "throw", side_effect=fake_throw
		), patch.object(module, "_", side_effect=lambda s: s), patch.object(
			module.frappe, "log_error"
		) as log_error:
			with self.assertRaises(RuntimeError):
				adapter._request(MagicMock(), "shipping", "POST", "/transport-orders", json_body={"a": 1})
		self.assertIn("Ninguno de los detalles", thrown[0])
		self.assertIn("[99] Contacto sin telefono", thrown[0])
		log_error.assert_called_once()
