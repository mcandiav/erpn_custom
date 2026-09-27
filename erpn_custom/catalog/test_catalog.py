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
from erpn_custom.catalog.seed import aduana_seed, normalize_text
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
		self.assertIn(("Sin talla", "", ""), seed_rows("Talla"))
		self.assertEqual(allowed_attributes("Maquillaje"), ["Color", "Tono", "Contenido"])
		self.assertEqual(allowed_attributes("Suplementos"), ["Color", "Contenido"])

	def test_seed_values_unique_per_attribute(self):
		for attribute in SEED_VALUES:
			values = [value.lower() for value, _dept, _family in seed_rows(attribute)]
			self.assertEqual(len(values), len(set(values)), attribute)

	def test_talla_labels_show_three_systems(self):
		rows = {value: (dept, family) for value, dept, family in seed_rows("Talla")}
		self.assertEqual(rows["US 8 · EU 39 · CL 38"], ("Mujer", "Calzado"))
		self.assertEqual(rows["US 8 · EU 41 · CL 40"], ("Hombre", "Calzado"))
		self.assertEqual(rows["M US 7 · W US 8.5 · EU 40 · CL 39"], ("Unisex", "Calzado"))
		self.assertEqual(rows["S · US 4-6 · EU 36-38"], ("Mujer", "Ropa"))
		self.assertEqual(rows["L (14-16)"], ("Niño/a", "Ropa"))
		self.assertEqual(rows["Talla única"], ("", ""))
		for dept, family in rows.values():
			self.assertIn(dept, ("", *DEPARTMENTS))
			self.assertIn(family, ("", "Calzado", "Ropa"))

	def test_talla_families_are_real(self):
		for _value, _dept, family in seed_rows("Talla"):
			if family:
				self.assertIn("Talla", FAMILY_ATTRIBUTES[family])

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


class TestAduana(unittest.TestCase):
	def test_normalize(self):
		self.assertEqual(normalize_text("  Botín   CAFÉ "), "botin cafe")
		self.assertEqual(normalize_text("Niño/a"), "nino/a")
		self.assertEqual(normalize_text(None), "")

	def test_seed_targets_exist(self):
		groups = {name for name, _parent, _is_group in iter_nodes()}
		for tipo, _text, value in aduana_seed():
			if tipo == "Tipo":
				self.assertIn(value, groups, value)
			elif tipo == "Color":
				self.assertIn(value, SEED_VALUES["Color"], value)
			elif tipo == "Departamento":
				self.assertIn(value, DEPARTMENTS, value)

	def test_seed_keys_unique(self):
		keys = [(tipo, normalize_text(text)) for tipo, text, _value in aduana_seed()]
		self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
	unittest.main()
