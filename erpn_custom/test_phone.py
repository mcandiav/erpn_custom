import unittest
from types import SimpleNamespace

from erpn_custom.phone import (
	normalize_address_phone,
	normalize_contact_phones,
	normalize_customer_mobile,
	normalize_phone,
)


class _Doc(dict):
	def get(self, key, default=None):
		return super().get(key, default)

	def set(self, key, value):
		self[key] = value


class TestNormalizePhone(unittest.TestCase):
	def test_strips_separators(self):
		self.assertEqual(normalize_phone("+56 9 5635 6441"), "+56956356441")
		self.assertEqual(normalize_phone("+56-9-4532.2217"), "+56945322217")
		self.assertEqual(normalize_phone("(+56) 9 8869\u00a07916"), "+56988697916")
		self.assertEqual(normalize_phone(" 988697916 "), "988697916")

	def test_keeps_clean_and_empty(self):
		self.assertEqual(normalize_phone("+56932107782"), "+56932107782")
		self.assertEqual(normalize_phone("56927274379"), "56927274379")
		self.assertEqual(normalize_phone(""), "")
		self.assertEqual(normalize_phone(None), "")


class TestPhoneHooks(unittest.TestCase):
	def test_contact_fields_and_rows(self):
		rows = [SimpleNamespace(phone="+56 9 4532 2217"), SimpleNamespace(phone=None)]
		doc = _Doc(mobile_no="+56 9 4532 2217", phone="", phone_nos=rows)
		normalize_contact_phones(doc)
		self.assertEqual(doc["mobile_no"], "+56945322217")
		self.assertEqual(doc["phone"], "")
		self.assertEqual(rows[0].phone, "+56945322217")
		self.assertIsNone(rows[1].phone)

	def test_address_phone(self):
		doc = _Doc(phone="+56 9 6835 3241")
		normalize_address_phone(doc)
		self.assertEqual(doc["phone"], "+56968353241")

	def test_customer_mobile(self):
		doc = _Doc(mobile_no=None)
		normalize_customer_mobile(doc)
		self.assertIsNone(doc["mobile_no"])
		doc = _Doc(mobile_no="+56 9 9092 8026")
		normalize_customer_mobile(doc)
		self.assertEqual(doc["mobile_no"], "+56990928026")


if __name__ == "__main__":
	unittest.main()
