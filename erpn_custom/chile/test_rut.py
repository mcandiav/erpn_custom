import unittest

from erpn_custom.chile.rut import normalize_chilean_tax_id


class TestNormalizeChileanTaxId(unittest.TestCase):
    def test_dotted_hyphen(self):
        self.assertEqual(normalize_chilean_tax_id("13.698.154-4"), "13698154-4")

    def test_already_canonical(self):
        self.assertEqual(normalize_chilean_tax_id("13698154-4"), "13698154-4")

    def test_spaces_and_lowercase_k(self):
        self.assertEqual(normalize_chilean_tax_id("  6-k "), "6-K")

    def test_invalid_checksum(self):
        self.assertIsNone(normalize_chilean_tax_id("13698154-5"))

    def test_empty_and_none(self):
        self.assertIsNone(normalize_chilean_tax_id(None))
        self.assertIsNone(normalize_chilean_tax_id("  "))
        self.assertIsNone(normalize_chilean_tax_id("abc"))


if __name__ == "__main__":
    unittest.main()
