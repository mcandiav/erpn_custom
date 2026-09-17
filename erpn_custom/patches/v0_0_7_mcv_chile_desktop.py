import frappe

from erpn_custom.chile.mcv_desktop_contract import (
	COURIER_CONFIGURATION,
	COURIER_ITEMS,
	COURIER_SIDEBAR,
	LEGACY_FOLDER,
	MANUAL_MCV,
	PAGOS_SIDEBAR,
	ROOT_FOLDER,
	is_workspace_placeholder,
)


def execute():
	_cleanup_manual_mcv_chile()
	_upsert_icon(
		{
			"doctype": "Desktop Icon",
			"label": ROOT_FOLDER,
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
			"restrict_removal": 0,
		}
	)
	_upsert_icon(
		{
			"doctype": "Desktop Icon",
			"label": PAGOS_SIDEBAR,
			"icon": "dollar-sign",
			"icon_type": "Link",
			"idx": 1,
			"link_to": PAGOS_SIDEBAR,
			"link_type": "Workspace Sidebar",
			"parent_icon": ROOT_FOLDER,
			"hidden": 0,
			"standard": 1,
			"app": "erpn_custom",
			"bg_color": "blue",
			"restrict_removal": 0,
		}
	)
	_upsert_courier_sidebar()
	_upsert_icon(
		{
			"doctype": "Desktop Icon",
			"label": COURIER_SIDEBAR,
			"icon": "truck",
			"icon_type": "Link",
			"idx": 2,
			"link_to": COURIER_SIDEBAR,
			"link_type": "Workspace Sidebar",
			"parent_icon": ROOT_FOLDER,
			"hidden": 0,
			"standard": 1,
			"app": "erpn_custom",
			"bg_color": "blue",
			"restrict_removal": 0,
		}
	)
	_remove_legacy_chile_folder()
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


def _cleanup_manual_mcv_chile():
	# Collation may equate "MCV CHILE" and "MCV Chile". Only remove the
	# non-standard manual Link artifact, never the standard Folder.
	for row in frappe.get_all(
		"Desktop Icon",
		fields=["name", "label", "standard", "icon_type", "app"],
	):
		label = (row.label or "").strip()
		if label.upper() != "MCV CHILE":
			continue
		if int(row.standard or 0) == 1 and row.icon_type == "Folder":
			continue
		if int(row.standard or 0) == 0 or row.icon_type == "Link":
			frappe.delete_doc("Desktop Icon", row.name, force=1, ignore_permissions=True)

	for row in frappe.get_all(
		"Workspace Sidebar",
		fields=["name", "title", "standard", "app"],
	):
		title = (row.title or row.name or "").strip()
		if title.upper() != "MCV CHILE":
			continue
		if int(row.standard or 0) == 1 and row.app == "erpn_custom":
			continue
		frappe.delete_doc("Workspace Sidebar", row.name, force=1, ignore_permissions=True)

	_delete_empty_workspace(MANUAL_MCV)


def _upsert_courier_sidebar():
	items = list(COURIER_ITEMS)
	if not frappe.db.exists("DocType", COURIER_CONFIGURATION):
		frappe.log_error(
			title="Spec 007: Courier Configuration missing",
			message="DocType Courier Configuration not found; Courier sidebar created without items.",
		)
		items = []

	values = {
		"doctype": "Workspace Sidebar",
		"title": COURIER_SIDEBAR,
		"header_icon": "truck",
		"module": "Chile",
		"standard": 1,
		"app": "erpn_custom",
	}
	if frappe.db.exists("Workspace Sidebar", COURIER_SIDEBAR):
		doc = frappe.get_doc("Workspace Sidebar", COURIER_SIDEBAR)
		doc.update(values)
		doc.set("items", items)
		doc.save(ignore_permissions=True)
		return
	doc = frappe.get_doc(values)
	doc.set("items", items)
	doc.insert(ignore_permissions=True)


def _remove_legacy_chile_folder():
	if not frappe.db.exists("Desktop Icon", LEGACY_FOLDER):
		return
	if LEGACY_FOLDER == ROOT_FOLDER:
		return
	try:
		frappe.delete_doc("Desktop Icon", LEGACY_FOLDER, force=1, ignore_permissions=True)
	except Exception:
		doc = frappe.get_doc("Desktop Icon", LEGACY_FOLDER)
		doc.hidden = 1
		doc.save(ignore_permissions=True)
		frappe.log_error(
			title="Spec 007: could not delete Desktop Icon Chile",
			message="Hidden Chile folder instead of delete.",
		)


def _upsert_icon(values):
	name = values["label"]
	if frappe.db.exists("Desktop Icon", name):
		doc = frappe.get_doc("Desktop Icon", name)
		doc.roles = []
		doc.update(values)
		doc.save(ignore_permissions=True)
		return
	frappe.get_doc(values).insert(ignore_permissions=True)


def _delete_desktop_icon(name):
	if frappe.db.exists("Desktop Icon", name):
		frappe.delete_doc("Desktop Icon", name, force=1, ignore_permissions=True)


def _delete_workspace_sidebar(name):
	if frappe.db.exists("Workspace Sidebar", name):
		frappe.delete_doc("Workspace Sidebar", name, force=1, ignore_permissions=True)


def _delete_empty_workspace(name):
	if not frappe.db.exists("Workspace", name):
		return
	doc = frappe.get_doc("Workspace", name)
	links = list(getattr(doc, "links", None) or [])
	shortcuts = list(getattr(doc, "shortcuts", None) or [])
	if not is_workspace_placeholder(doc.content) or links or shortcuts:
		frappe.log_error(
			title="Spec 007: Workspace MCV CHILE not empty",
			message=(
				f"Preserved Workspace {name!r}: content_len={len(doc.content or '')}, "
				f"links={len(links)}, shortcuts={len(shortcuts)}"
			),
		)
		return
	frappe.delete_doc("Workspace", name, force=1, ignore_permissions=True)
