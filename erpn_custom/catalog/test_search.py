import sys
import unittest
from unittest.mock import MagicMock

# Host unittest without Frappe installed.
_frappe = MagicMock()
_frappe.utils.flt = lambda v: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)
_frappe.whitelist = lambda *a, **k: (lambda f: f)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.catalog.search import available_qty, build_filters, departments_for  # noqa: E402
from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM  # noqa: E402


class TestDepartments(unittest.TestCase):
	def test_women_and_men_include_unisex(self):
		self.assertEqual(departments_for("Mujer"), ["Mujer", "Unisex"])
		self.assertEqual(departments_for("Hombre"), ["Hombre", "Unisex"])

	def test_other_departments_are_exact(self):
		self.assertEqual(departments_for("Unisex"), ["Unisex"])
		self.assertEqual(departments_for("Niño/a"), ["Niño/a"])


class TestFilters(unittest.TestCase):
	def test_base_excludes_placeholder_and_disabled(self):
		filters = build_filters()
		self.assertEqual(filters["disabled"], 0)
		self.assertEqual(filters["name"], ["!=", ENCARGO_PENDIENTE_ITEM])
		self.assertNotIn("item_group", filters)

	def test_group_subtree(self):
		self.assertEqual(build_filters(["Bolsos", "Cartera"])["item_group"], ["in", ["Bolsos", "Cartera"]])

	def test_unknown_group_matches_nothing(self):
		self.assertEqual(build_filters([])["item_group"], ["in", [""]])

	def test_facets(self):
		filters = build_filters(
			brand="Guess",
			departamento="Mujer",
			attributes={"custom_color": "Black · Negro · Preto", "custom_tamano": "", "item_name": "x"},
		)
		self.assertEqual(filters["brand"], "Guess")
		self.assertEqual(filters["custom_departamento"], ["in", ["Mujer", "Unisex"]])
		self.assertEqual(filters["custom_color"], "Black · Negro · Preto")
		self.assertNotIn("custom_tamano", filters)
		self.assertNotIn("item_name", filters)


class TestStock(unittest.TestCase):
	def test_available_discounts_reservations(self):
		self.assertEqual(available_qty(16, 2), 14)
		self.assertEqual(available_qty(1, None), 1)

	def test_available_never_negative(self):
		self.assertEqual(available_qty(1, 3), 0)


if __name__ == "__main__":
	unittest.main()
