import frappe

SELLING_SIDEBAR = "Selling"
ENCARGO_LINK = {
	"type": "Link",
	"link_type": "DocType",
	"link_to": "Encargo",
	"label": "Encargos (ENC)",
	"icon": "shopping-bag",
	"child": 0,
}


def ensure_encargo_link():
	"""after_migrate: ERPNext re-syncs its Selling sidebar, so re-add Encargos (ENC) below Sales Order."""
	if not frappe.db.exists("Workspace Sidebar", SELLING_SIDEBAR):
		return
	doc = frappe.get_doc("Workspace Sidebar", SELLING_SIDEBAR)
	if not insert_encargo_link(doc):
		return
	# in_import stops export_sidebar from writing into the erpnext app folder in developer_mode.
	previous = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		doc.save(ignore_permissions=True)
	finally:
		frappe.flags.in_import = previous


def insert_encargo_link(doc):
	"""Place the Encargo link right after the top-level Sales Order link. Returns True if doc changed."""
	items = doc.items
	if any(row.link_type == "DocType" and row.link_to == "Encargo" for row in items):
		return False
	anchor = next(
		(
			pos
			for pos, row in enumerate(items)
			if row.link_type == "DocType" and row.link_to == "Sales Order" and not row.child
		),
		None,
	)
	if anchor is None:
		return False
	row = doc.append("items", dict(ENCARGO_LINK))
	items.remove(row)
	items.insert(anchor + 1, row)
	for idx, item in enumerate(items, start=1):
		item.idx = idx
	return True
