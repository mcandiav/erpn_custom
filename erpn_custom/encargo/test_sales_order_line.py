import sys
import unittest
from unittest.mock import MagicMock, patch

# Host unittest without Frappe installed; the stub must not leak into other test modules.
with patch.dict(sys.modules, {"frappe": sys.modules.get("frappe") or MagicMock()}):
	from erpn_custom.encargo import sales_order_line


class _Row(dict):
	def get(self, key, default=None):
		return super().get(key, default)

	def __getattr__(self, key):
		return self.get(key)


def _encargo(**values):
	return _Row(
		{
			"source_type": "UNKNOWN_ITEM",
			"sales_order": "OV-2026-00001",
			"sales_order_item": "r9eebj7pss",
			"description": "Prueba de color",
			"brand": "Marc Jacobs",
			"item_group": "Crossbody",
			"custom_departamento": "Mujer",
			"custom_tamano": "Medium",
			"custom_color": "Black · Negro · Preto",
			"reference_image": "/private/files/imagebfb2db.png",
			**values,
		}
	)


def _fake_frappe(docstatus=0):
	fake = MagicMock()
	fake.db.get_value.return_value = docstatus
	return fake


class TestLineDescription(unittest.TestCase):
	def setUp(self):
		patcher = patch.object(sales_order_line, "_", side_effect=lambda text: text)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_summary_follows_description(self):
		self.assertEqual(
			sales_order_line.line_description(_encargo()),
			"Prueba de color — Marca: Marc Jacobs | Grupo: Crossbody | Departamento: Mujer"
			" | Color: Black · Negro · Preto | Tamaño: Medium",
		)

	def test_without_characteristics_keeps_description(self):
		encargo = _Row({"description": " Enc1 "})
		self.assertEqual(sales_order_line.line_description(encargo), "Enc1")

	def test_line_values_carry_image(self):
		values = sales_order_line.line_values(_encargo(reference_image=None))
		self.assertIsNone(values["image"])


class TestSyncSalesOrderLine(unittest.TestCase):
	def _sync(self, encargo, docstatus=0):
		fake = _fake_frappe(docstatus)
		with patch.object(sales_order_line, "frappe", fake), patch.object(sales_order_line, "_", side_effect=lambda t: t):
			sales_order_line.sync_sales_order_line(encargo)
		return fake

	def test_draft_order_line_is_updated(self):
		fake = self._sync(_encargo())
		doctype, name, values = fake.db.set_value.call_args.args
		self.assertEqual((doctype, name), ("Sales Order Item", "r9eebj7pss"))
		self.assertEqual(values["image"], "/private/files/imagebfb2db.png")
		self.assertTrue(values["description"].startswith("Prueba de color — Marca: Marc Jacobs"))

	def test_submitted_order_line_is_left_alone(self):
		self.assertFalse(self._sync(_encargo(), docstatus=1).db.set_value.called)

	def test_known_item_line_is_left_alone(self):
		self.assertFalse(self._sync(_encargo(source_type="KNOWN_ITEM")).db.set_value.called)

	def test_without_line_does_nothing(self):
		self.assertFalse(self._sync(_encargo(sales_order_item=None)).db.set_value.called)


class TestRefreshEncargoLines(unittest.TestCase):
	def test_only_encargo_lines_are_refreshed(self):
		encargo_line = _Row({"item_code": "ENCARGO-PENDIENTE", "custom_encargo": "ENC-2026-00006"})
		stock_line = _Row({"item_code": "Notengocodigo", "description": "Notengocodigo"})
		doc = MagicMock()
		doc.items = [encargo_line, stock_line]
		fake = MagicMock()
		fake.db.get_value.return_value = _encargo()
		with patch.object(sales_order_line, "frappe", fake), patch.object(sales_order_line, "_", side_effect=lambda t: t):
			sales_order_line.refresh_encargo_lines(doc)
		self.assertTrue(encargo_line["description"].startswith("Prueba de color — "))
		self.assertEqual(encargo_line["image"], "/private/files/imagebfb2db.png")
		self.assertEqual(stock_line["description"], "Notengocodigo")
		fake.db.get_value.assert_called_once()


if __name__ == "__main__":
	unittest.main()
