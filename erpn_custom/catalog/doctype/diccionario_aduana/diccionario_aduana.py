import frappe
from frappe import _
from frappe.model.document import Document

from erpn_custom.catalog.aduana import validate_target
from erpn_custom.catalog.seed import normalize_text


class DiccionarioAduana(Document):
	def autoname(self):
		self.texto = normalize_text(self.texto)
		self.name = f"{self.tipo_dato}: {self.texto}"

	def validate(self):
		self.texto = normalize_text(self.texto)
		if not self.texto:
			frappe.throw(_("Texto original is required"))
		if self.estado == "Clasificado":
			validate_target(self.tipo_dato, self.valor_erp)
		else:
			self.valor_erp = None
