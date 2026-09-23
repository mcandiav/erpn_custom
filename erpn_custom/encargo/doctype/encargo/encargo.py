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
		self._apply_brand_store_pair()

	def before_insert(self):
		if not self.purchase_status:
			self.purchase_status = "PENDING"
		if not self.reception_status:
			self.reception_status = "PENDING"
		if not self.status:
			self.status = "Draft"
		# New unknown ENC must pick an enabled Brand+Store pair.
		if self.source_type == "UNKNOWN_ITEM" and not self.encargo_brand_store:
			frappe.throw(frappe._("Brand / Store pair is required for new Encargo"))

	def _apply_brand_store_pair(self):
		if not self.encargo_brand_store:
			return
		pair = frappe.db.get_value(
			"Encargo Brand Store",
			self.encargo_brand_store,
			["brand", "store", "enabled"],
			as_dict=True,
		)
		if not pair:
			frappe.throw(frappe._("Brand / Store pair {0} not found").format(self.encargo_brand_store))
		if not pair.get("enabled"):
			frappe.throw(frappe._("Brand / Store pair {0} is disabled").format(self.encargo_brand_store))
		if frappe.db.get_value("Encargo Store", pair.get("store"), "enabled") == 0:
			frappe.throw(frappe._("Store {0} is disabled").format(pair.get("store")))
		self.brand = pair.get("brand")
		self.suggested_store = pair.get("store")
