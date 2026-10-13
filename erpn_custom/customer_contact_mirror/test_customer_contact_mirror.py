import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Host unittest without Frappe installed.
_frappe = MagicMock()
_frappe.utils.cstr = lambda v: "" if v is None else str(v)
_frappe.whitelist = lambda *a, **k: (lambda f: f)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.customer_contact_mirror import service  # noqa: E402
from erpn_custom.customer_contact_mirror.service import (  # noqa: E402
	_apply_payload,
	create_mirror_contact,
	is_individual_customer,
	mirror_payload_from_customer,
	split_customer_name,
)


class _Doc(dict):
	def get(self, key, default=None):
		return super().get(key, default)


class _Contact:
	def __init__(self, phone_nos=None):
		self.name = "Cynthia Contreras Soto-Cynthia Contreras Soto"
		self.phone_nos = phone_nos or []
		self.email_ids = []
		self.links = []
		self.inserted = False

	def get(self, key, default=None):
		return getattr(self, key, default)

	def set(self, key, value):
		setattr(self, key, value)

	def append(self, key, row):
		getattr(self, key).append(SimpleNamespace(**row))

	def insert(self, ignore_permissions=False):
		self.inserted = True


class TestMirrorPrimaryInMemory(unittest.TestCase):
	def test_create_sets_primary_on_doc(self):
		doc = _Doc(customer_name="Cynthia Contreras Soto", mobile_no="+56 9 2727 4379", email_id="")
		doc.name = "Cynthia Contreras Soto"
		contact = _Contact()
		fake = MagicMock()
		fake.new_doc.return_value = contact
		fake.db.get_value.return_value = None
		fake.db.has_column.return_value = True
		with patch.object(service, "frappe", fake):
			name = create_mirror_contact(doc)
		self.assertTrue(contact.inserted)
		self.assertEqual(doc.customer_primary_contact, name)
		fake.db.set_value.assert_called_once()

	def test_apply_payload_reuses_row_written_with_spaces(self):
		row = SimpleNamespace(phone="+56 9 2727 4379", is_primary_mobile_no=0)
		contact = _Contact(phone_nos=[row])
		payload = {"first_name": "Cynthia", "last_name": "", "email_id": "", "mobile_no": "+56927274379"}
		fake = MagicMock()
		fake.db.has_column.return_value = False
		with patch.object(service, "frappe", fake):
			_apply_payload(contact, payload)
		self.assertEqual(len(contact.phone_nos), 1)
		self.assertEqual(row.phone, "+56927274379")
		self.assertEqual(row.is_primary_mobile_no, 1)


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

	def test_mirror_payload_normalizes_mobile(self):
		payload = mirror_payload_from_customer(
			_Doc(customer_name="Zully Yojanna Garcia", mobile_no="+56 9 5635 6441")
		)
		self.assertEqual(payload["mobile_no"], "+56956356441")

	def test_mirror_payload_without_contact_data(self):
		payload = mirror_payload_from_customer(_Doc(customer_name="Solo Nombre", email_id="", mobile_no=None))
		self.assertEqual(payload["first_name"], "Solo")
		self.assertEqual(payload["last_name"], "Nombre")
		self.assertEqual(payload["email_id"], "")
		self.assertEqual(payload["mobile_no"], "")


if __name__ == "__main__":
	unittest.main()
