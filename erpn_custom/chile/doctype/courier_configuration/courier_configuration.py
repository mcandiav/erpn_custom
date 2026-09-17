import frappe
from frappe import _
from frappe.model.document import Document


class CourierConfiguration(Document):
	def validate(self):
		self._validate_unique_provider_environment()
		self._validate_unique_credential_keys()

	def _validate_unique_provider_environment(self):
		filters = {
			"provider": self.provider,
			"environment": self.environment,
			"name": ("!=", self.name),
		}
		if frappe.db.exists("Courier Configuration", filters):
			frappe.throw(
				_("Ya existe una Courier Configuration para {0} / {1}").format(
					self.provider, self.environment
				)
			)

	def _validate_unique_credential_keys(self):
		seen = set()
		for row in self.credentials or []:
			key = (row.credential_key or "").strip()
			if not key:
				continue
			if key in seen:
				frappe.throw(_("credential_key duplicado: {0}").format(key))
			seen.add(key)
