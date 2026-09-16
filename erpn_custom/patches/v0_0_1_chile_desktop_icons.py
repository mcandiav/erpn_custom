import frappe

SIDEBAR_NAME = "Pagos de Clientes"

SIDEBAR_ITEMS = [
    {
        "type": "Link",
        "label": "Pagos de Clientes",
        "link_type": "Workspace",
        "link_to": "Pagos de Clientes",
        "child": 0,
        "collapsible": 0,
        "indent": 0,
        "keep_closed": 0,
        "show_arrow": 0,
    },
    {
        "type": "Link",
        "label": "Pagos de Clientes / Vinculador",
        "link_type": "Page",
        "link_to": "pagos-de-clientes",
        "child": 0,
        "collapsible": 0,
        "indent": 0,
        "keep_closed": 0,
        "show_arrow": 0,
    },
    {
        "type": "Link",
        "label": "Configuración del Vinculador",
        "link_type": "DocType",
        "link_to": "Deposit Mapping Settings",
        "child": 0,
        "collapsible": 0,
        "indent": 0,
        "keep_closed": 0,
        "show_arrow": 0,
    },
    {
        "type": "Link",
        "label": "Historial de Vinculación",
        "link_type": "DocType",
        "link_to": "Deposit Mapping Run",
        "child": 0,
        "collapsible": 0,
        "indent": 0,
        "keep_closed": 0,
        "show_arrow": 0,
    },
    {
        "type": "Link",
        "label": "Historial de Intentos",
        "link_type": "DocType",
        "link_to": "Deposit Mapping Attempt",
        "child": 0,
        "collapsible": 0,
        "indent": 0,
        "keep_closed": 0,
        "show_arrow": 0,
    },
]


def execute():
    _upsert_sidebar()
    _upsert_icon(
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
    _upsert_icon(
        {
            "doctype": "Desktop Icon",
            "label": "Pagos de Clientes",
            "icon": "dollar-sign",
            "icon_type": "Link",
            "idx": 1,
            "link_to": SIDEBAR_NAME,
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


def _upsert_sidebar():
    values = {
        "doctype": "Workspace Sidebar",
        "title": SIDEBAR_NAME,
        "header_icon": "money-coins-1",
        "module": "Chile",
        "standard": 1,
        "app": "erpn_custom",
    }
    if frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
        doc = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
        doc.update(values)
        doc.set("items", SIDEBAR_ITEMS)
        doc.save(ignore_permissions=True)
        return
    doc = frappe.get_doc(values)
    doc.set("items", SIDEBAR_ITEMS)
    doc.insert(ignore_permissions=True)


def _upsert_icon(values):
    name = values["label"]
    if frappe.db.exists("Desktop Icon", name):
        doc = frappe.get_doc("Desktop Icon", name)
        doc.roles = []
        doc.update(values)
        doc.save(ignore_permissions=True)
        return
    frappe.get_doc(values).insert(ignore_permissions=True)
