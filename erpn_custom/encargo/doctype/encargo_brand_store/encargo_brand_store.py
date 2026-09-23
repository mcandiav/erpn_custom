import frappe
from frappe.model.document import Document


class EncargoBrandStore(Document):
	def validate(self):
		if not self.brand or not self.store:
			return
		filters = {"brand": self.brand, "store": self.store}
		if not self.is_new():
			filters["name"] = ["!=", self.name]
		if frappe.db.exists("Encargo Brand Store", filters):
			frappe.throw(
				frappe._("Pair {0} + {1} already exists").format(self.brand, self.store)
			)
		if frappe.db.get_value("Encargo Store", self.store, "enabled") == 0:
			frappe.throw(frappe._("Store {0} is disabled").format(self.store))
