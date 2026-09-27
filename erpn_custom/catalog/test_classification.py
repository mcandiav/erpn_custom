import sys
import unittest
from unittest.mock import MagicMock, patch

# Host unittest without Frappe installed; the stub must not leak into other test modules.
with patch.dict(sys.modules, {"frappe": sys.modules.get("frappe") or MagicMock()}):
	from erpn_custom.catalog import item as catalog_item

PARENTS = {"Bota": "Calzado", "Calzado": "Vestuario", "Vestuario": "All Item Groups", "Cartera": "Bolsos", "Bolsos": "Accesorios", "Accesorios": "All Item Groups"}
LISTS = {("Talla", "US 7.5 · EU 38.5 · CL 37.5"), ("Tamaño", "Medium"), ("Color", "Black · Negro · Preto")}


class _Doc(dict):
	def __getattr__(self, key):
		return self.get(key)

	def __setattr__(self, key, value):
		self[key] = value

	def set(self, key, value):
		self[key] = value


class TestApplyClassification(unittest.TestCase):
	def _apply(self, doc):
		fake = MagicMock()
		fake.db.get_value.side_effect = lambda doctype, name, field: PARENTS.get(name)
		fake.db.exists.side_effect = lambda doctype, filters: (filters["parent"], filters["attribute_value"]) in LISTS
		fake.throw.side_effect = ValueError
		with patch.object(catalog_item, "frappe", fake), patch.object(catalog_item, "_", lambda s: s):
			catalog_item.apply_classification(doc)
		return doc

	def test_familia_from_group(self):
		self.assertEqual(self._apply(_Doc(item_group="Bota")).custom_familia, "Calzado")

	def test_drops_attribute_of_other_family(self):
		doc = self._apply(_Doc(item_group="Bota", custom_talla="US 7.5 · EU 38.5 · CL 37.5", custom_tamano="Medium"))
		self.assertEqual(doc.custom_talla, "US 7.5 · EU 38.5 · CL 37.5")
		self.assertIsNone(doc.custom_tamano)

	def test_rejects_value_outside_list(self):
		with self.assertRaises(ValueError):
			self._apply(_Doc(item_group="Cartera", custom_color="Violeta inventado"))

	def test_bag_keeps_size_and_color(self):
		doc = self._apply(_Doc(item_group="Cartera", custom_tamano="Medium", custom_color="Black · Negro · Preto"))
		self.assertEqual((doc.custom_familia, doc.custom_tamano), ("Bolsos", "Medium"))


if __name__ == "__main__":
	unittest.main()
