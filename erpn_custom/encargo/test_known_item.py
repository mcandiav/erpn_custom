import sys
import unittest
from unittest.mock import MagicMock, patch

# Host unittest without Frappe installed; the stub must not leak into other test modules.
with patch.dict(sys.modules, {"frappe": sys.modules.get("frappe") or MagicMock()}):
	from erpn_custom.encargo import known_item


class _Row(dict):
	def get(self, key, default=None):
		return super().get(key, default)


def _item(**values):
	return _Row(
		{
			"item_name": "Bota Blake de Combate de Gamuza",
			"brand": "Michael Kors",
			"custom_color": "Brown · Café · Marrom",
			"custom_talla": "US 7.5 · EU 38.5 · CL 37.5",
			"custom_tamano": None,
			**values,
		}
	)


class TestKnownItemValues(unittest.TestCase):
	def _values(self, item):
		fake = MagicMock()
		fake.db.get_value.return_value = item
		fake.throw.side_effect = ValueError
		with patch.object(known_item, "frappe", fake):
			return known_item.known_item_values("198446906618")

	def test_fields_come_from_item(self):
		values = self._values(_item(item_group="Bota", custom_departamento="Mujer", custom_taco="Bajo"))
		self.assertEqual(values["brand"], "Michael Kors")
		self.assertEqual(values["size"], "US 7.5 · EU 38.5 · CL 37.5")
		self.assertEqual(values["color"], "Brown · Café · Marrom")
		self.assertEqual(values["description"], "Bota Blake de Combate de Gamuza")
		self.assertIsNone(values["model"])
		self.assertEqual(values["item_group"], "Bota")
		self.assertEqual(values["custom_departamento"], "Mujer")
		self.assertEqual(values["custom_talla"], "US 7.5 · EU 38.5 · CL 37.5")
		self.assertEqual(values["custom_taco"], "Bajo")
		self.assertIsNone(values["custom_manga"])

	def test_legacy_text_from_lists(self):
		self.assertEqual(
			known_item.legacy_size_color({"custom_tamano": "Medium", "custom_color": "Black · Negro · Preto"}),
			{"size": "Medium", "color": "Black · Negro · Preto"},
		)
		self.assertEqual(known_item.legacy_size_color({}), {"size": None, "color": None})

	def test_bag_uses_tamano_as_size(self):
		values = self._values(_item(custom_talla=None, custom_tamano="Medium"))
		self.assertEqual(values["size"], "Medium")

	def test_missing_item_throws(self):
		with self.assertRaises(ValueError):
			self._values(None)

	def test_covers_every_locked_field(self):
		self.assertEqual(set(self._values(_item())), set(known_item.KNOWN_ITEM_FIELDS))


if __name__ == "__main__":
	unittest.main()
