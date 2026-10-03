from frappe.model.document import Document

from erpn_custom.chile.known_payer import validate_known_payer


class KnownPayer(Document):
	def validate(self):
		validate_known_payer(self)
