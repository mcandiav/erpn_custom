import unittest
from types import SimpleNamespace

from erpn_custom.naming.series import DOCUMENT_SERIES, series_options, set_return_series


class FakeDoc(SimpleNamespace):
	def get(self, key, default=None):
		return getattr(self, key, default)


class TestDocumentSeries(unittest.TestCase):
	def test_all_series_reset_yearly(self):
		for doctype, (default, return_series) in DOCUMENT_SERIES.items():
			self.assertTrue(default.endswith("-.YYYY.-"), doctype)
			if return_series:
				self.assertTrue(return_series.endswith("-.YYYY.-"), doctype)

	def test_prefixes_are_unique(self):
		prefixes = [s for pair in DOCUMENT_SERIES.values() for s in pair if s]
		self.assertEqual(len(prefixes), len(set(prefixes)))

	def test_sales_order_is_ov(self):
		self.assertEqual(series_options("Sales Order"), ["OV-.YYYY.-"])

	def test_invoice_options_default_first(self):
		self.assertEqual(series_options("Sales Invoice"), ["FAC-.YYYY.-", "NC-.YYYY.-"])

	def test_return_invoice_gets_credit_note_series(self):
		doc = FakeDoc(doctype="Sales Invoice", is_return=1, naming_series="FAC-.YYYY.-")
		set_return_series(doc)
		self.assertEqual(doc.naming_series, "NC-.YYYY.-")

	def test_regular_invoice_untouched(self):
		doc = FakeDoc(doctype="Sales Invoice", is_return=0, naming_series="FAC-.YYYY.-")
		set_return_series(doc)
		self.assertEqual(doc.naming_series, "FAC-.YYYY.-")

	def test_return_delivery_note(self):
		doc = FakeDoc(doctype="Delivery Note", is_return=1, naming_series="NE-.YYYY.-")
		set_return_series(doc)
		self.assertEqual(doc.naming_series, "NE-DEV-.YYYY.-")

	def test_doctype_without_return_series_untouched(self):
		doc = FakeDoc(doctype="Sales Order", is_return=1, naming_series="OV-.YYYY.-")
		set_return_series(doc)
		self.assertEqual(doc.naming_series, "OV-.YYYY.-")


if __name__ == "__main__":
	unittest.main()
