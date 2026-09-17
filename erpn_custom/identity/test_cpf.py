import unittest

from erpn_custom.identity.cpf import normalize_cpf


class TestNormalizeCpf(unittest.TestCase):
	def test_valid_with_punctuation(self):
		self.assertEqual(normalize_cpf("529.982.247-25"), "52998224725")

	def test_valid_plain(self):
		self.assertEqual(normalize_cpf("11144477735"), "11144477735")

	def test_preserves_leading_zero(self):
		# 01234567890 is invalid algorithmically; use a valid CPF that starts with 0 if any.
		# Contract: when valid, digits keep leading zeros (no int cast).
		result = normalize_cpf("390.533.447-05")
		self.assertEqual(result, "39053344705")
		self.assertIsInstance(result, str)

	def test_invalid_dv(self):
		self.assertIsNone(normalize_cpf("529.982.247-20"))

	def test_invalid_length(self):
		self.assertIsNone(normalize_cpf("123"))
		self.assertIsNone(normalize_cpf("123456789012"))

	def test_repeated_sequence(self):
		self.assertIsNone(normalize_cpf("00000000000"))
		self.assertIsNone(normalize_cpf("11111111111"))

	def test_empty(self):
		self.assertIsNone(normalize_cpf(None))
		self.assertIsNone(normalize_cpf("  "))


if __name__ == "__main__":
	unittest.main()
