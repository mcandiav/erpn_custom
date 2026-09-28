import frappe
from frappe.model.document import Document

from erpn_custom.catalog.item import apply_classification
from erpn_custom.encargo.brand_supplier import optional_supplier_for_brand, require_brand
from erpn_custom.encargo.known_item import known_item_values, legacy_size_color
from erpn_custom.encargo.sales_order_line import sync_sales_order_line


class Encargo(Document):
	def validate(self):
		if self.requested_qty is not None and self.requested_qty <= 0:
			frappe.throw(frappe._("Requested Qty must be greater than 0"))
		if self.source_type == "KNOWN_ITEM" and not self.expected_item:
			frappe.throw(frappe._("Expected Item is required for known-item Encargo"))
		if self.source_type == "UNKNOWN_ITEM" and self.expected_item:
			frappe.throw(frappe._("Unknown-item Encargo must not set Expected Item"))
		if self.source_type == "KNOWN_ITEM":
			self.update(known_item_values(self.expected_item))
		apply_classification(self)
		# Encargos created before the lists keep their text size/color.
		if self.item_group:
			self.update(legacy_size_color(self.as_dict()))
		if not (self.description or "").strip():
			frappe.throw(frappe._("Description is required"))
		if self.brand or self.supplier:
			brand, supplier = optional_supplier_for_brand(self.brand, self.supplier)
			self.brand = brand
			self.supplier = supplier

	def on_update(self):
		sync_sales_order_line(self)

	def before_insert(self):
		if not self.purchase_status:
			self.purchase_status = "PENDING"
		if not self.reception_status:
			self.reception_status = "PENDING"
		if not self.status:
			self.status = "Draft"
		if self.source_type == "UNKNOWN_ITEM":
			self.brand = require_brand(self.brand)
			require_leaf_group(self.item_group)


def require_leaf_group(item_group):
	if not item_group:
		frappe.throw(frappe._("Grupo de producto es obligatorio."), title=frappe._("Falta el grupo de producto"))
	if frappe.db.get_value("Item Group", item_group, "is_group"):
		frappe.throw(
			frappe._("«{0}» no es un tipo: elige el último nivel del árbol.").format(item_group),
			title=frappe._("Grupo de producto"),
		)
