import sys
import unittest
from unittest.mock import MagicMock

# Host unittest without Frappe installed.
_frappe = MagicMock()
_frappe.utils.cstr = lambda v: "" if v is None else str(v)
_frappe.whitelist = lambda *a, **k: (lambda f: f)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.customer_contact_mirror.service import (  # noqa: E402
	is_individual_customer,
	mirror_payload_from_customer,
	split_customer_name,
)


class _Doc(dict):
	def get(self, key, default=None):
		return super().get(key, default)


class TestCustomerContactMirror(unittest.TestCase):
	def test_is_individual_only(self):
		self.assertTrue(is_individual_customer(_Doc(customer_type="Individual")))
		self.assertFalse(is_individual_customer(_Doc(customer_type="Company")))
		self.assertFalse(is_individual_customer(_Doc(customer_type="")))

	def test_split_customer_name(self):
		self.assertEqual(split_customer_name("Cynthia Contreras Soto"), ("Cynthia", "Contreras Soto"))
		self.assertEqual(split_customer_name("Madonna"), ("Madonna", ""))
		self.assertEqual(split_customer_name("  "), ("Cliente", ""))

	def test_mirror_payload(self):
		payload = mirror_payload_from_customer(
			_Doc(
				customer_name="Cynthia Contreras Soto",
				email_id="cynthia@gmail.com",
				mobile_no="56927274379",
			)
		)
		self.assertEqual(payload["first_name"], "Cynthia")
		self.assertEqual(payload["last_name"], "Contreras Soto")
		self.assertEqual(payload["email_id"], "cynthia@gmail.com")
		self.assertEqual(payload["mobile_no"], "56927274379")

	def test_mirror_payload_without_contact_data(self):
		payload = mirror_payload_from_customer(_Doc(customer_name="Solo Nombre", email_id="", mobile_no=None))
		self.assertEqual(payload["first_name"], "Solo")
		self.assertEqual(payload["last_name"], "Nombre")
		self.assertEqual(payload["email_id"], "")
		self.assertEqual(payload["mobile_no"], "")


if __name__ == "__main__":
	unittest.main()
