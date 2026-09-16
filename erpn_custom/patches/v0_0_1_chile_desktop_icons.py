import os

import frappe
from frappe.modules.import_file import import_file_by_path


def execute():
    sidebar_path = frappe.get_app_path("erpn_custom", "workspace_sidebar", "pagos_de_clientes.json")
    if os.path.exists(sidebar_path):
        import_file_by_path(sidebar_path, force=True, ignore_version=True)

    _upsert(
        {
            "doctype": "Desktop Icon",
            "label": "Chile",
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
    _upsert(
        {
            "doctype": "Desktop Icon",
            "label": "Pagos de Clientes",
            "icon": "dollar-sign",
            "icon_type": "Link",
            "idx": 1,
            "link_to": "Pagos de Clientes",
            "link_type": "Workspace Sidebar",
            "parent_icon": "Chile",
            "hidden": 0,
            "standard": 1,
            "app": "erpn_custom",
            "bg_color": "blue",
            "restrict_removal": 0,
        }
    )
    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")


def _upsert(values):
    name = values["label"]
    if frappe.db.exists("Desktop Icon", name):
        doc = frappe.get_doc("Desktop Icon", name)
        doc.roles = []
        doc.update(values)
        doc.save(ignore_permissions=True)
        return
    frappe.get_doc(values).insert(ignore_permissions=True)
