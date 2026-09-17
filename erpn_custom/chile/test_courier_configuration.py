import os
import unittest

from erpn_custom.chile.courier_credentials import STANDARD_COURIER_CREDENTIAL_KEYS


class TestCourierCredentialContract(unittest.TestCase):
	def test_standard_credential_keys(self):
		self.assertEqual(
			STANDARD_COURIER_CREDENTIAL_KEYS,
			("coverage_api_key", "rating_api_key", "shipping_api_key"),
		)

	def test_default_rows_include_endpoint_slot(self):
		from erpn_custom.chile.courier_credentials import default_credential_rows

		rows = default_credential_rows()
		self.assertEqual(len(rows), 3)
		self.assertEqual(
			[row["credential_key"] for row in rows],
			list(STANDARD_COURIER_CREDENTIAL_KEYS),
		)

	def test_env_example_is_optional_reference_only(self):
		root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
		path = os.path.join(root, ".env.example")
		self.assertTrue(os.path.exists(path))


try:
	import frappe
	from frappe.tests.utils import FrappeTestCase
except Exception:  # pragma: no cover
	FrappeTestCase = None


if FrappeTestCase is not None:

	class TestCourierConfigurationModel(FrappeTestCase):
		def tearDown(self):
			for name in frappe.get_all(
				"Courier Configuration",
				filters={"provider": "chilexpress"},
				pluck="name",
			):
				frappe.delete_doc("Courier Configuration", name, force=1, ignore_permissions=True)
			if frappe.db.exists("Courier Provider", "chilexpress-test-tmp"):
				frappe.delete_doc("Courier Provider", "chilexpress-test-tmp", force=1, ignore_permissions=True)
			frappe.db.commit()

		def _ensure_provider(self):
			if frappe.db.exists("Courier Provider", "chilexpress"):
				return "chilexpress"
			doc = frappe.get_doc(
				{
					"doctype": "Courier Provider",
					"provider_name": "Chilexpress",
					"provider_code": "chilexpress",
					"enabled": 1,
				}
			).insert(ignore_permissions=True)
			return doc.name

		def test_default_rows_and_endpoint_resolution(self):
			from erpn_custom.chile.courier_endpoints import get_courier_endpoint

			provider = self._ensure_provider()
			cfg = frappe.get_doc(
				{
					"doctype": "Courier Configuration",
					"provider": provider,
					"environment": "Test",
					"enabled": 1,
				}
			).insert(ignore_permissions=True)
			keys = {row.credential_key for row in cfg.credentials}
			self.assertEqual(
				keys,
				{"coverage_api_key", "rating_api_key", "shipping_api_key"},
			)
			for row in cfg.credentials:
				if row.credential_key == "coverage_api_key":
					row.endpoint_url = "https://example.test/coverage"
					row.secret_value = "fake-coverage"
			cfg.save(ignore_permissions=True)

			url = get_courier_endpoint("chilexpress", "Test", "coverage")
			self.assertEqual(url, "https://example.test/coverage")

			dup = frappe.get_doc(
				{
					"doctype": "Courier Configuration",
					"provider": provider,
					"environment": "Test",
					"enabled": 1,
				}
			)
			with self.assertRaises(frappe.ValidationError):
				dup.insert(ignore_permissions=True)

		def test_provider_can_be_disabled(self):
			code = "chilexpress-test-tmp"
			doc = frappe.get_doc(
				{
					"doctype": "Courier Provider",
					"provider_name": "Tmp",
					"provider_code": code,
					"enabled": 1,
				}
			).insert(ignore_permissions=True)
			doc.enabled = 0
			doc.save(ignore_permissions=True)
			self.assertEqual(frappe.db.get_value("Courier Provider", code, "enabled"), 0)
