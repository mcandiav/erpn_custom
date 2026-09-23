import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


_frappe.throw = _throw
sys.modules.setdefault("frappe", _frappe)

from erpn_custom.encargo.brand_supplier import (  # noqa: E402
	optional_supplier_for_brand,
	require_brand,
	supplier_supplies_brand,
)


class TestBrandSupplier(unittest.TestCase):
	def test_require_brand_empty(self):
		with self.assertRaises(Exception):
			require_brand("")

	@patch("erpn_custom.encargo.brand_supplier.frappe.db.exists", return_value=True)
	def test_require_brand_ok(self, _exists):
		self.assertEqual(require_brand("Michael Kors"), "Michael Kors")

	@patch("erpn_custom.encargo.brand_supplier.frappe.db.exists", return_value=True)
	def test_supplier_supplies_brand(self, exists):
		self.assertTrue(supplier_supplies_brand("Ross", "Michael Kors"))
		exists.assert_called()

	@patch("erpn_custom.encargo.brand_supplier.frappe.db.get_value", return_value=0)
	@patch("erpn_custom.encargo.brand_supplier.supplier_supplies_brand", return_value=True)
	@patch("erpn_custom.encargo.brand_supplier.frappe.db.exists", return_value=True)
	def test_optional_supplier_with_match(self, _exists, _supplies, _disabled):
		brand, supplier = optional_supplier_for_brand("Michael Kors", "Ross")
		self.assertEqual(brand, "Michael Kors")
		self.assertEqual(supplier, "Ross")

	@patch("erpn_custom.encargo.brand_supplier.frappe.db.exists", return_value=True)
	def test_optional_supplier_omitted(self, _exists):
		brand, supplier = optional_supplier_for_brand("Michael Kors", None)
		self.assertEqual(brand, "Michael Kors")
		self.assertIsNone(supplier)

	@patch("erpn_custom.encargo.brand_supplier.frappe.db.get_value", return_value=0)
	@patch("erpn_custom.encargo.brand_supplier.supplier_supplies_brand", return_value=False)
	@patch("erpn_custom.encargo.brand_supplier.frappe.db.exists", return_value=True)
	def test_optional_supplier_wrong_brand_throws(self, _exists, _supplies, _disabled):
		with self.assertRaises(Exception):
			optional_supplier_for_brand("Zadig", "Ross")


if __name__ == "__main__":
	unittest.main()
