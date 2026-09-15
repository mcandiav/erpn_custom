import unittest

from erpn_custom.chile.matching import (
    CONFLICT,
    EXACT_TAX_ID,
    NO_MATCH,
    classify_rut,
    index_customers_by_normalized_tax_id,
)
from erpn_custom.chile.rut import normalize_chilean_tax_id


class TestMatching(unittest.TestCase):
    def setUp(self):
        self.indexed = index_customers_by_normalized_tax_id(
            [
                {"name": "Cynthia Contreras Soto", "tax_id": "13698154-4"},
                {"name": "Dup A", "tax_id": "11.111.111-1"},
                {"name": "Dup B", "tax_id": "11111111-1"},
            ],
            normalize_chilean_tax_id,
        )

    def test_exact_one_customer(self):
        rule, names = classify_rut("13698154-4", self.indexed)
        self.assertEqual(rule, EXACT_TAX_ID)
        self.assertEqual(names, ["Cynthia Contreras Soto"])

    def test_no_customer(self):
        rule, names = classify_rut("7686939-K", self.indexed)
        self.assertEqual(rule, NO_MATCH)
        self.assertEqual(names, [])

    def test_conflict(self):
        key = normalize_chilean_tax_id("11.111.111-1")
        rule, names = classify_rut(key, self.indexed)
        self.assertEqual(rule, CONFLICT)
        self.assertEqual(set(names), {"Dup A", "Dup B"})

    def test_invalid_rut(self):
        rule, names = classify_rut(None, self.indexed)
        self.assertEqual(rule, NO_MATCH)
        self.assertEqual(names, [])


if __name__ == "__main__":
    unittest.main()
