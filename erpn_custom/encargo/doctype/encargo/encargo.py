import frappe
from frappe.model.document import Document


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
		self._validate_brand_supplier()

	def before_insert(self):
		if not self.purchase_status:
			self.purchase_status = "PENDING"
		if not self.reception_status:
			self.reception_status = "PENDING"
		if not self.status:
			self.status = "Draft"
		if self.source_type == "UNKNOWN_ITEM":
			if not self.brand or not self.supplier:
				frappe.throw(frappe._("Brand and Supplier are required for new Encargo"))

	def _validate_brand_supplier(self):
		if self.brand and not frappe.db.exists("Brand", self.brand):
			frappe.throw(frappe._("Brand {0} not found").format(self.brand))
		if self.supplier and not frappe.db.exists("Supplier", self.supplier):
			frappe.throw(frappe._("Supplier {0} not found").format(self.supplier))
