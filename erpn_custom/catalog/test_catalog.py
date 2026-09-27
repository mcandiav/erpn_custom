import unicodedata
import unittest

from erpn_custom.catalog.attributes import (
	ATTRIBUTE_FIELDS,
	DEPARTMENTS,
	FAMILY_ATTRIBUTES,
	SEED_VALUES,
	allowed_attributes,
	make_abbr,
	seed_rows,
)
from erpn_custom.catalog.tree import CLASSIFICATION_TREE, ROOT, family_from_chain, iter_nodes


def _key(name):
	return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()


class TestTree(unittest.TestCase):
	def test_counts(self):
		families = [f for fams in CLASSIFICATION_TREE.values() for f in fams]
		self.assertEqual(list(CLASSIFICATION_TREE), ["Vestuario", "Accesorios", "Belleza", "Otros"])
		self.assertEqual(len(families), 13)

	def test_names_unique_ignoring_accents_and_case(self):
		names = [name for name, _parent, _is_group in iter_nodes()]
		self.assertEqual(len(names), len({_key(n) for n in names}))

	def test_parents_come_first(self):
		seen = {ROOT}
		for name, parent, _is_group in iter_nodes():
			self.assertIn(parent, seen)
			seen.add(name)

	def test_leaf_families(self):
		nodes = {name: is_group for name, _parent, is_group in iter_nodes()}
		self.assertEqual(nodes["Lentes"], 0)
		self.assertEqual(nodes["Hogar y otros"], 0)
		self.assertEqual(nodes["Calzado"], 1)

	def test_family_from_chain(self):
		self.assertEqual(family_from_chain(["Bota", "Calzado", "Vestuario"]), "Calzado")
		self.assertEqual(family_from_chain(["Lentes", "Accesorios"]), "Lentes")
		self.assertIsNone(family_from_chain(["Vestuario"]))
		self.assertIsNone(family_from_chain(["Botas"]))
		self.assertIsNone(family_from_chain(["Bota", "Calzado", "Otros"]))


class TestAttributes(unittest.TestCase):
	def test_family_attributes_are_known(self):
		for family, attributes in FAMILY_ATTRIBUTES.items():
			self.assertTrue(any(family in fams for fams in CLASSIFICATION_TREE.values()))
			for attribute in attributes:
				self.assertIn(attribute, ATTRIBUTE_FIELDS)

	def test_allowed_attributes(self):
		self.assertEqual(allowed_attributes("Calzado"), ["Color", "Talla", "Taco"])
		self.assertEqual(allowed_attributes("Bolsos"), ["Color", "Tamaño"])
		self.assertEqual(allowed_attributes(None), ["Color"])

	def test_seed_covers_every_attribute(self):
		self.assertEqual(set(SEED_VALUES), set(ATTRIBUTE_FIELDS))
		self.assertIn(("Sin talla", ""), seed_rows("Talla"))
		self.assertEqual(allowed_attributes("Maquillaje"), ["Color", "Tono", "Contenido"])
		self.assertEqual(allowed_attributes("Suplementos"), ["Color", "Contenido"])

	def test_seed_values_unique_per_attribute(self):
		for attribute in SEED_VALUES:
			values = [value.lower() for value, _dept in seed_rows(attribute)]
			self.assertEqual(len(values), len(set(values)), attribute)

	def test_talla_labels_show_three_systems(self):
		rows = dict(seed_rows("Talla"))
		self.assertEqual(rows["US 8 · EU 39 · CL 38"], "Mujer")
		self.assertEqual(rows["US 8 · EU 41 · CL 40"], "Hombre")
		self.assertEqual(rows["M US 7 · W US 8.5 · EU 40 · CL 39"], "Unisex")
		self.assertEqual(rows["S · US 4-6 · EU 36-38"], "Mujer")
		self.assertEqual(rows["L (14-16)"], "Niño/a")
		for value, dept in rows.items():
			self.assertIn(dept, ("", *DEPARTMENTS))

	def test_color_records_are_multilingual(self):
		self.assertIn("Black · Negro · Preto", SEED_VALUES["Color"])
		self.assertIn("Multicolor", SEED_VALUES["Color"])

	def test_abbr_unique_and_short(self):
		taken = []
		for value in ["Sin taco", "Sin talla", "Sin talla!", "Niño/a", "Sin talla"]:
			abbr = make_abbr(value, taken)
			self.assertLessEqual(len(abbr), 10)
			self.assertNotIn(abbr.lower(), [t.lower() for t in taken])
			taken.append(abbr)
		self.assertEqual(taken[0], "SINTACO")
		self.assertEqual(taken[3], "NINOA")


if __name__ == "__main__":
	unittest.main()
