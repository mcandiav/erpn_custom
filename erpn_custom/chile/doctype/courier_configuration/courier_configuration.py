import frappe
from frappe import _
from frappe.model.document import Document

from erpn_custom.chile.courier_credentials import STANDARD_COURIER_CREDENTIAL_KEYS


class CourierConfiguration(Document):
	def before_insert(self):
		self.ensure_default_credentials()

	def validate(self):
		self.ensure_default_credentials()
		self._validate_unique_provider_environment()
		self._validate_unique_credential_keys()
		self._validate_standard_credential_keys()

	def ensure_default_credentials(self):
		existing = {(row.credential_key or "").strip() for row in (self.credentials or [])}
		for key in STANDARD_COURIER_CREDENTIAL_KEYS:
			if key not in existing:
				self.append("credentials", {"credential_key": key})

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

	def _validate_standard_credential_keys(self):
		allowed = set(STANDARD_COURIER_CREDENTIAL_KEYS)
		for row in self.credentials or []:
			key = (row.credential_key or "").strip()
			if key and key not in allowed:
				frappe.throw(
					_("credential_key no estandar: {0}. Use: {1}").format(
						key, ", ".join(STANDARD_COURIER_CREDENTIAL_KEYS)
					)
				)
