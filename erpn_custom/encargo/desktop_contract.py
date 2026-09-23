ENCARGO_SIDEBAR = "Encargo"
ENCARGO_STORE = "Encargo Store"
ENCARGO_BRAND_STORE = "Encargo Brand Store"
ENCARGO_DOCTYPE = "Encargo"

ENCARGO_ITEMS = [
	{
		"type": "Link",
		"label": "Tienda Encargo",
		"link_type": "DocType",
		"link_to": ENCARGO_STORE,
		"icon": "store",
		"child": 0,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	},
	{
		"type": "Link",
		"label": "Marca / Tienda Encargo",
		"link_type": "DocType",
		"link_to": ENCARGO_BRAND_STORE,
		"icon": "tag",
		"child": 0,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	},
	{
		"type": "Link",
		"label": "Encargo",
		"link_type": "DocType",
		"link_to": ENCARGO_DOCTYPE,
		"icon": "file-text",
		"child": 0,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	},
	{
		"type": "Link",
		"label": "Marca",
		"link_type": "DocType",
		"link_to": "Brand",
		"icon": "award",
		"child": 0,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	},
]
