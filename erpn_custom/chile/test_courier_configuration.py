import os
import unittest

from erpn_custom.chile.courier_endpoints import endpoint_env_name


class TestCourierEndpointNaming(unittest.TestCase):
	def test_chilexpress_test_and_prod_names(self):
		self.assertEqual(
			endpoint_env_name("chilexpress", "Test", "coverage"),
			"CHILEXPRESS_TEST_COVERAGE_URL",
		)
		self.assertEqual(
			endpoint_env_name("chilexpress", "Producción", "shipping"),
			"CHILEXPRESS_PROD_SHIPPING_URL",
		)

	def test_standard_credential_keys(self):
		from erpn_custom.chile.courier_credentials import STANDARD_COURIER_CREDENTIAL_KEYS

		self.assertEqual(
			STANDARD_COURIER_CREDENTIAL_KEYS,
			("coverage_api_key", "rating_api_key", "shipping_api_key"),
		)

	def test_env_example_documents_expected_keys(self):
		root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
		path = os.path.join(root, ".env.example")
		with open(path, encoding="utf-8") as handle:
			content = handle.read()
		for key in (
			"CHILEXPRESS_TEST_COVERAGE_URL",
			"CHILEXPRESS_TEST_RATING_URL",
			"CHILEXPRESS_TEST_SHIPPING_URL",
			"CHILEXPRESS_PROD_COVERAGE_URL",
			"CHILEXPRESS_PROD_RATING_URL",
			"CHILEXPRESS_PROD_SHIPPING_URL",
		):
			self.assertIn(key, content)


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

		def test_provider_environment_unicity_and_credentials(self):
			provider = self._ensure_provider()
			cfg = frappe.get_doc(
				{
					"doctype": "Courier Configuration",
					"provider": provider,
					"environment": "Test",
					"enabled": 1,
					"credentials": [
						{"credential_key": "coverage_api_key", "secret_value": "fake-coverage"},
						{"credential_key": "rating_api_key", "secret_value": "fake-rating"},
					],
				}
			).insert(ignore_permissions=True)

			prod = frappe.get_doc(
				{
					"doctype": "Courier Configuration",
					"provider": provider,
					"environment": "Producción",
					"enabled": 1,
				}
			).insert(ignore_permissions=True)
			self.assertNotEqual(cfg.name, prod.name)
			prod_keys = {row.credential_key for row in prod.credentials}
			self.assertEqual(
				prod_keys,
				{"coverage_api_key", "rating_api_key", "shipping_api_key"},
			)

			loaded = frappe.get_doc("Courier Configuration", cfg.name)
			keys = {row.credential_key for row in loaded.credentials}
			self.assertEqual(
				keys,
				{"coverage_api_key", "rating_api_key", "shipping_api_key"},
			)

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

			secret_row = next(
				row for row in loaded.credentials if row.credential_key == "coverage_api_key"
			)
			secret = secret_row.get_password("secret_value", raise_exception=False)
			self.assertTrue(bool(secret))
			self.assertNotEqual(secret, "******")

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

		def test_patch_sidebar_points_to_configuration(self):
			from erpn_custom.chile.mcv_desktop_contract import COURIER_SIDEBAR
			from erpn_custom.patches.v0_0_8_courier_configuration import execute

			execute()
			execute()
			self.assertTrue(frappe.db.exists("Courier Provider", "chilexpress"))
			self.assertTrue(frappe.db.exists("Workspace Sidebar", COURIER_SIDEBAR))
			sidebar = frappe.get_doc("Workspace Sidebar", COURIER_SIDEBAR)
			self.assertEqual(len(sidebar.items), 1)
			self.assertEqual(sidebar.items[0].link_to, "Courier Configuration")
			self.assertEqual(sidebar.items[0].label, "Configuración de Couriers")
			self.assertFalse(frappe.db.exists("DocType", "Chilexpress Settings"))
