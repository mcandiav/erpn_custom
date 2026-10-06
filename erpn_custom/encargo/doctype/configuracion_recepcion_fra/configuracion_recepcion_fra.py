import frappe
from frappe import _
from frappe.model.document import Document

from erpn_custom.encargo.inventory import clearing_account_problem, reception_company


class ConfiguracionRecepcionFRA(Document):
	def validate(self):
		if not self.clearing_account:
			return
		account = frappe.db.get_value(
			"Account", self.clearing_account, ["company", "is_group", "account_type"], as_dict=True
		)
		problem = clearing_account_problem(account, reception_company())
		if problem:
			frappe.throw(problem, title=_("Cuenta transitoria"))
