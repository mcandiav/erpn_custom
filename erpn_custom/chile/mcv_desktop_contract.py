ROOT_FOLDER = "MCV Chile"
MANUAL_MCV = "MCV CHILE"
PAGOS_SIDEBAR = "Pagos de Clientes"
COURIER_SIDEBAR = "Courier"
CHILEXPRESS_SETTINGS = "Chilexpress Settings"
LEGACY_FOLDER = "Chile"

COURIER_ITEMS = [
	{
		"type": "Link",
		"label": "Chilexpress Settings",
		"link_type": "DocType",
		"link_to": CHILEXPRESS_SETTINGS,
		"child": 0,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	},
]


def is_workspace_placeholder(content):
	text = (content or "").strip()
	return text in ("", "[]", "{}", "null")
