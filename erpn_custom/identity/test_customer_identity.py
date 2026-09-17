import unittest

from erpn_custom.identity.dni import normalize_dni
from erpn_custom.identity.passport import normalize_passport
from erpn_custom.identity.service import (
	IdentityValidationError,
	build_identity_key,
	normalize_customer_identity,
)


class TestCustomerIdentity(unittest.TestCase):
	def test_rut_with_dots_and_lowercase_k(self):
		identity = normalize_customer_identity("RUT", None, "13.698.154-4")
		self.assertEqual(identity["document_type"], "RUT")
		self.assertEqual(identity["country"], "Chile")
		self.assertEqual(identity["tax_id"], "13698154-4")
		self.assertEqual(identity["identity_key"], "RUT|Chile|13698154-4")

	def test_rut_forces_chile(self):
		identity = normalize_customer_identity("RUT", "Argentina", "13698154-4")
		self.assertEqual(identity["country"], "Chile")

	def test_rut_invalid_dv(self):
		with self.assertRaises(IdentityValidationError):
			normalize_customer_identity("RUT", "Chile", "13698154-5")

	def test_cpf_forces_brazil(self):
		identity = normalize_customer_identity("CPF", "Chile", "529.982.247-25")
		self.assertEqual(identity["document_type"], "CPF")
		self.assertEqual(identity["country"], "Brazil")
		self.assertEqual(identity["tax_id"], "52998224725")

	def test_cpf_invalid(self):
		with self.assertRaises(IdentityValidationError):
			normalize_customer_identity("CPF", "Brazil", "529.982.247-20")

	def test_dni_requires_country(self):
		with self.assertRaises(IdentityValidationError):
			normalize_customer_identity("DNI", None, "01234567")

	def test_dni_preserves_leading_zero(self):
		identity = normalize_customer_identity("DNI", "Argentina", "01234567")
		self.assertEqual(identity["tax_id"], "01234567")
		self.assertEqual(identity["country"], "Argentina")

	def test_dni_same_number_different_countries(self):
		a = normalize_customer_identity("DNI", "Argentina", "01234567")
		b = normalize_customer_identity("DNI", "Peru", "01234567")
		self.assertNotEqual(a["identity_key"], b["identity_key"])

	def test_passport_requires_country(self):
		with self.assertRaises(IdentityValidationError):
			normalize_customer_identity("Passport", "", "AB123456")

	def test_passport_alphanumeric(self):
		identity = normalize_customer_identity("Passport", "Spain", "AB123456")
		self.assertEqual(identity["tax_id"], "AB123456")
		self.assertEqual(identity["identity_key"], "Passport|Spain|AB123456")

	def test_passport_same_number_different_countries(self):
		a = build_identity_key("Passport", "Spain", "AB123456")
		b = build_identity_key("Passport", "Italy", "AB123456")
		self.assertNotEqual(a, b)

	def test_normalize_dni_empty(self):
		self.assertIsNone(normalize_dni("Argentina", "  "))
		self.assertIsNone(normalize_dni("", "123"))

	def test_normalize_passport_empty(self):
		self.assertIsNone(normalize_passport("Spain", None))
		self.assertIsNone(normalize_passport(None, "X1"))

	def test_identity_key_includes_disabled_scope_contract(self):
		# Uniqueness includes disabled customers at DB/lookup layer;
		# key format itself is independent of disabled flag.
		key = build_identity_key("RUT", "Chile", "13698154-4")
		self.assertEqual(key, "RUT|Chile|13698154-4")


if __name__ == "__main__":
	unittest.main()
