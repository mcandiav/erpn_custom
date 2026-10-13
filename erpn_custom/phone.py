import re


SEPARATORS = re.compile(r"[\s\-\.\(\)]+")


def normalize_phone(value):
	if value is None:
		return ""
	return SEPARATORS.sub("", str(value))


def _normalize_field(doc, fieldname):
	value = doc.get(fieldname)
	if value:
		doc.set(fieldname, normalize_phone(value))


def normalize_contact_phones(doc, method=None):
	"""Hook: Contact validate."""
	_normalize_field(doc, "mobile_no")
	_normalize_field(doc, "phone")
	for row in doc.get("phone_nos") or []:
		if row.phone:
			row.phone = normalize_phone(row.phone)


def normalize_address_phone(doc, method=None):
	"""Hook: Address validate."""
	_normalize_field(doc, "phone")


def normalize_customer_mobile(doc, method=None):
	"""Hook: Customer validate."""
	_normalize_field(doc, "mobile_no")
