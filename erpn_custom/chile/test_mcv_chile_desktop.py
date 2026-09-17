import unittest

from erpn_custom.chile.mcv_desktop_contract import (
	COURIER_ITEMS,
	COURIER_SIDEBAR,
	LEGACY_FOLDER,
	MANUAL_MCV,
	PAGOS_SIDEBAR,
	ROOT_FOLDER,
	is_workspace_placeholder,
)


class TestMCVChileDesktopHelpers(unittest.TestCase):
	def test_root_label_is_mcv_chile(self):
		self.assertEqual(ROOT_FOLDER, "MCV Chile")
		self.assertNotEqual(ROOT_FOLDER, MANUAL_MCV)
		self.assertEqual(LEGACY_FOLDER, "Chile")

	def test_courier_sidebar_contract(self):
		self.assertEqual(COURIER_SIDEBAR, "Courier")
		self.assertEqual(PAGOS_SIDEBAR, "Pagos de Clientes")
		self.assertEqual(len(COURIER_ITEMS), 1)
		item = COURIER_ITEMS[0]
		self.assertEqual(item["type"], "Link")
		self.assertEqual(item["link_type"], "DocType")
		self.assertEqual(item["link_to"], "Chilexpress Settings")
		self.assertEqual(item["label"], "Chilexpress Settings")

	def test_workspace_placeholder_detection(self):
		self.assertTrue(is_workspace_placeholder(None))
		self.assertTrue(is_workspace_placeholder(""))
		self.assertTrue(is_workspace_placeholder("[]"))
		self.assertTrue(is_workspace_placeholder(" {} "))
		self.assertTrue(is_workspace_placeholder("null"))
		self.assertFalse(is_workspace_placeholder('[{"id":"x"}]'))
		self.assertFalse(is_workspace_placeholder("not-empty"))


try:
	import frappe
	from frappe.tests.utils import FrappeTestCase
except Exception:  # pragma: no cover - offline / non-bench runs
	FrappeTestCase = None


if FrappeTestCase is not None:

	class TestMCVChileDesktopPatch(FrappeTestCase):
		def setUp(self):
			self._purge_related()
			frappe.get_doc(
				{
					"doctype": "Desktop Icon",
					"label": LEGACY_FOLDER,
					"icon": "earth",
					"icon_type": "Folder",
					"idx": 0,
					"link_to": "",
					"link_type": "Workspace Sidebar",
					"parent_icon": "",
					"hidden": 0,
					"standard": 1,
					"app": "erpn_custom",
					"bg_color": "blue",
				}
			).insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "Desktop Icon",
					"label": PAGOS_SIDEBAR,
					"icon": "dollar-sign",
					"icon_type": "Link",
					"idx": 1,
					"link_to": PAGOS_SIDEBAR,
					"link_type": "Workspace Sidebar",
					"parent_icon": LEGACY_FOLDER,
					"hidden": 0,
					"standard": 1,
					"app": "erpn_custom",
					"bg_color": "blue",
				}
			).insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "Desktop Icon",
					"label": MANUAL_MCV,
					"icon_type": "Link",
					"idx": 0,
					"link_to": MANUAL_MCV,
					"link_type": "Workspace Sidebar",
					"parent_icon": "",
					"hidden": 0,
					"standard": 0,
					"bg_color": "gray",
				}
			).insert(ignore_permissions=True)
			if not frappe.db.exists("Workspace Sidebar", PAGOS_SIDEBAR):
				frappe.get_doc(
					{
						"doctype": "Workspace Sidebar",
						"title": PAGOS_SIDEBAR,
						"header_icon": "money-coins-1",
						"module": "Chile",
						"standard": 1,
						"app": "erpn_custom",
						"items": [],
					}
				).insert(ignore_permissions=True)
			frappe.db.commit()

		def tearDown(self):
			self._purge_related()
			frappe.db.commit()

		def _purge_related(self):
			from erpn_custom.patches.v0_0_7_mcv_chile_desktop import (
				_delete_desktop_icon,
				_delete_workspace_sidebar,
			)

			for name in (COURIER_SIDEBAR, PAGOS_SIDEBAR, ROOT_FOLDER, MANUAL_MCV, LEGACY_FOLDER):
				_delete_desktop_icon(name)
			for name in (COURIER_SIDEBAR, MANUAL_MCV):
				_delete_workspace_sidebar(name)

		def test_topology_and_idempotency(self):
			from erpn_custom.patches.v0_0_7_mcv_chile_desktop import execute

			execute()
			execute()

			self.assertTrue(frappe.db.exists("Desktop Icon", ROOT_FOLDER))
			root = frappe.get_doc("Desktop Icon", ROOT_FOLDER)
			self.assertEqual(root.icon_type, "Folder")
			self.assertEqual(root.standard, 1)
			self.assertEqual(root.app, "erpn_custom")
			self.assertFalse(root.parent_icon)
			self.assertEqual(root.hidden, 0)

			pagos = frappe.get_doc("Desktop Icon", PAGOS_SIDEBAR)
			self.assertEqual(pagos.parent_icon, ROOT_FOLDER)
			self.assertEqual(pagos.link_to, PAGOS_SIDEBAR)
			self.assertEqual(pagos.link_type, "Workspace Sidebar")

			self.assertTrue(frappe.db.exists("Desktop Icon", COURIER_SIDEBAR))
			courier_icon = frappe.get_doc("Desktop Icon", COURIER_SIDEBAR)
			self.assertEqual(courier_icon.parent_icon, ROOT_FOLDER)
			self.assertEqual(courier_icon.link_to, COURIER_SIDEBAR)

			self.assertTrue(frappe.db.exists("Workspace Sidebar", COURIER_SIDEBAR))
			courier = frappe.get_doc("Workspace Sidebar", COURIER_SIDEBAR)
			self.assertEqual(courier.module, "Chile")
			self.assertEqual(courier.app, "erpn_custom")
			self.assertEqual(len(courier.items), 1)
			self.assertEqual(courier.items[0].link_type, "DocType")
			self.assertEqual(courier.items[0].link_to, "Chilexpress Settings")

			if frappe.db.exists("Desktop Icon", LEGACY_FOLDER):
				legacy = frappe.get_doc("Desktop Icon", LEGACY_FOLDER)
				self.assertEqual(legacy.hidden, 1)

			self.assertEqual(root.label, ROOT_FOLDER)
			self.assertEqual(root.standard, 1)
