import frappe
from frappe.model.document import Document

from erpn_custom.encargo.brand_supplier import optional_supplier_for_brand, require_brand


class Encargo(Document):
	def validate(self):
		if self.requested_qty is not None and self.requested_qty <= 0:
			frappe.throw(frappe._("Requested Qty must be greater than 0"))
		if self.source_type == "KNOWN_ITEM" and not self.expected_item:
			frappe.throw(frappe._("Expected Item is required for known-item Encargo"))
		if self.source_type == "UNKNOWN_ITEM" and self.expected_item:
			frappe.throw(frappe._("Unknown-item Encargo must not set Expected Item"))
		if not (self.description or "").strip():
			frappe.throw(frappe._("Description is required"))
		if self.brand or self.supplier:
			brand, supplier = optional_supplier_for_brand(self.brand, self.supplier)
			self.brand = brand
			self.supplier = supplier

	def before_insert(self):
		if not self.purchase_status:
			self.purchase_status = "PENDING"
		if not self.reception_status:
			self.reception_status = "PENDING"
		if not self.status:
			self.status = "Draft"
		if self.source_type == "UNKNOWN_ITEM":
			self.brand = require_brand(self.brand)
