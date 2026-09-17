import unittest

from erpn_custom.chile.matching import (
    CONFLICT,
    EXACT_TAX_ID,
    NO_MATCH,
    classify_rut,
    index_customers_by_normalized_tax_id,
)
from erpn_custom.chile.rut import normalize_chilean_tax_id
from erpn_custom.identity.filters import chile_rut_customer_filters


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

    def test_foreign_documents_excluded_from_rut_index(self):
        # Spec 006: only RUT/Chile customers are selected before indexing.
        mixed = [
            {"name": "RUT Chile", "tax_id": "13698154-4", "custom_tax_id_type": "RUT", "custom_tax_id_country": "Chile"},
            {"name": "DNI Lookalike", "tax_id": "13698154", "custom_tax_id_type": "DNI", "custom_tax_id_country": "Argentina"},
            {"name": "CPF Lookalike", "tax_id": "52998224725", "custom_tax_id_type": "CPF", "custom_tax_id_country": "Brazil"},
            {"name": "Passport", "tax_id": "AB123456", "custom_tax_id_type": "Passport", "custom_tax_id_country": "Spain"},
        ]
        filters = chile_rut_customer_filters()
        eligible = [
            c
            for c in mixed
            if c["custom_tax_id_type"] == filters["custom_tax_id_type"]
            and c["custom_tax_id_country"] == filters["custom_tax_id_country"]
        ]
        indexed = index_customers_by_normalized_tax_id(eligible, normalize_chilean_tax_id)
        self.assertEqual(list(indexed.keys()), ["13698154-4"])
        self.assertEqual(indexed["13698154-4"], ["RUT Chile"])
        self.assertNotIn("52998224725", indexed)


if __name__ == "__main__":
    unittest.main()
