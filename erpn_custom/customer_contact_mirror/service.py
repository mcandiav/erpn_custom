import frappe
from frappe.utils import cstr


MIRROR_FIELD = "custom_is_customer_mirror"


def is_individual_customer(doc):
	return cstr(doc.get("customer_type")).strip() == "Individual"


def split_customer_name(full_name):
	parts = cstr(full_name).strip().split(None, 1)
	if not parts:
		return "Cliente", ""
	if len(parts) == 1:
		return parts[0], ""
	return parts[0], parts[1]


def mirror_payload_from_customer(doc):
	first_name, last_name = split_customer_name(doc.get("customer_name") or doc.get("name"))
	return {
		"first_name": first_name,
		"last_name": last_name,
		"email_id": cstr(doc.get("email_id")).strip(),
		"mobile_no": cstr(doc.get("mobile_no")).strip(),
	}


def _linked_contact_names(customer_name):
	rows = frappe.get_all(
		"Dynamic Link",
		filters={
			"parenttype": "Contact",
			"link_doctype": "Customer",
			"link_name": customer_name,
		},
		pluck="parent",
	)
	return list(dict.fromkeys(rows))


def find_mirror_contact(customer_name):
	linked = _linked_contact_names(customer_name)

	if frappe.db.has_column("Contact", MIRROR_FIELD):
		for name in linked:
			if frappe.db.get_value("Contact", name, MIRROR_FIELD):
				return name

	primary = frappe.db.get_value("Customer", customer_name, "customer_primary_contact")
	if primary and frappe.db.exists("Contact", primary):
		return primary

	for name in linked:
		if frappe.db.get_value("Contact", name, "is_primary_contact"):
			return name

	if linked:
		return linked[0]
	return None


def _apply_payload(contact, payload):
	contact.first_name = payload["first_name"]
	contact.last_name = payload["last_name"] or ""

	email = payload["email_id"]
	mobile = payload["mobile_no"]

	if email:
		contact.email_id = email
		existing = None
		for row in contact.get("email_ids") or []:
			if cstr(row.email_id).strip().lower() == email.lower():
				existing = row
				break
		if existing:
			existing.is_primary = 1
		else:
			contact.set("email_ids", [])
			contact.append("email_ids", {"email_id": email, "is_primary": 1})
	else:
		contact.email_id = None

	if mobile:
		contact.mobile_no = mobile
		existing = None
		for row in contact.get("phone_nos") or []:
			if cstr(row.phone).strip() == mobile:
				existing = row
				break
		if existing:
			existing.is_primary_mobile_no = 1
		else:
			contact.set("phone_nos", [])
			contact.append(
				"phone_nos",
				{"phone": mobile, "is_primary_mobile_no": 1, "is_primary_phone": 0},
			)
	else:
		contact.mobile_no = None

	if frappe.db.has_column("Contact", MIRROR_FIELD):
		contact.set(MIRROR_FIELD, 1)
	contact.is_primary_contact = 1


def _ensure_customer_link(contact, customer_name):
	for row in contact.get("links") or []:
		if row.link_doctype == "Customer" and row.link_name == customer_name:
			return
	contact.append("links", {"link_doctype": "Customer", "link_name": customer_name})


def _set_customer_primary(customer_name, contact_name):
	current = frappe.db.get_value("Customer", customer_name, "customer_primary_contact")
	if current == contact_name:
		return
	frappe.db.set_value(
		"Customer",
		customer_name,
		"customer_primary_contact",
		contact_name,
		update_modified=False,
	)


def create_mirror_contact(doc):
	payload = mirror_payload_from_customer(doc)
	contact = frappe.new_doc("Contact")
	_apply_payload(contact, payload)
	_ensure_customer_link(contact, doc.name)
	contact.insert(ignore_permissions=True)
	_set_customer_primary(doc.name, contact.name)
	return contact.name


def sync_mirror_contact(contact_name, doc):
	contact = frappe.get_doc("Contact", contact_name)
	_apply_payload(contact, mirror_payload_from_customer(doc))
	_ensure_customer_link(contact, doc.name)
	contact.flags.ignore_permissions = True
	contact.save()
	_set_customer_primary(doc.name, contact.name)
	return contact.name


def ensure_customer_contact_mirror(doc, method=None):
	"""Hook: after_insert / on_update for Customer."""
	if frappe.flags.get("in_customer_contact_mirror"):
		return
	if not is_individual_customer(doc):
		return
	if doc.get("disabled"):
		# Still keep mirror if exists; do not create for new disabled? Spec: no auto-delete.
		# Create/sync even if disabled so historical Individual stays usable.
		pass

	frappe.flags.in_customer_contact_mirror = True
	try:
		existing = find_mirror_contact(doc.name)
		if existing:
			sync_mirror_contact(existing, doc)
		else:
			create_mirror_contact(doc)
	finally:
		frappe.flags.in_customer_contact_mirror = False


def list_individuals_needing_mirror():
	customers = frappe.get_all(
		"Customer",
		filters={"customer_type": "Individual"},
		fields=["name", "customer_name", "email_id", "mobile_no", "customer_primary_contact"],
	)
	needed = []
	for row in customers:
		if find_mirror_contact(row.name):
			continue
		needed.append(row.name)
	return needed


def backfill_customer_contact_mirrors(dry_run=True):
	"""Create mirrors for Individual customers without a linked Contact. Idempotent."""
	dry_run = bool(int(dry_run)) if not isinstance(dry_run, bool) else dry_run
	needed = list_individuals_needing_mirror()
	summary = {
		"dry_run": dry_run,
		"candidates": len(needed),
		"created": 0,
		"adopted_synced": 0,
		"errors": 0,
		"error_samples": [],
	}
	if dry_run:
		return summary

	for name in needed:
		try:
			doc = frappe.get_doc("Customer", name)
			ensure_customer_contact_mirror(doc)
			summary["created"] += 1
		except Exception as exc:
			summary["errors"] += 1
			if len(summary["error_samples"]) < 20:
				summary["error_samples"].append({"customer": name, "error": cstr(exc)})

	# Second pass: adopt/sync any Individual that already had a contact but no flag
	individuals = frappe.get_all("Customer", filters={"customer_type": "Individual"}, pluck="name")
	for name in individuals:
		try:
			mirror = find_mirror_contact(name)
			if not mirror:
				continue
			if frappe.db.has_column("Contact", MIRROR_FIELD) and not frappe.db.get_value(
				"Contact", mirror, MIRROR_FIELD
			):
				doc = frappe.get_doc("Customer", name)
				sync_mirror_contact(mirror, doc)
				summary["adopted_synced"] += 1
		except Exception as exc:
			summary["errors"] += 1
			if len(summary["error_samples"]) < 20:
				summary["error_samples"].append({"customer": name, "error": cstr(exc)})

	frappe.logger("erpn_custom").info("customer_contact_mirror_backfill summary={0}".format(summary))
	return summary


@frappe.whitelist()
def run_backfill(dry_run=1):
	"""Desk/bench callable backfill. Pass dry_run=0 to write."""
	return backfill_customer_contact_mirrors(dry_run=dry_run)
