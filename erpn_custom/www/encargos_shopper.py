import frappe
from frappe import _

from erpn_custom.encargo.shopper import is_shopper

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/encargos-shopper"
		raise frappe.Redirect
	if not is_shopper(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	context.no_cache = 1
	context.show_sidebar = False
	context.title = _("Encargos por comprar")
