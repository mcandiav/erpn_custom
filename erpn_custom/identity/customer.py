import frappe

from erpn_custom.identity.filters import chile_rut_customer_filters
from erpn_custom.identity.service import (
	IdentityValidationError,
	build_identity_key,
	normalize_customer_identity,
)

# Re-export for callers/tests that import from this module.
__all__ = [
	"IdentityValidationError",
	"apply_customer_identity",
	"assert_identity_unique",
	"build_identity_key",
	"chile_rut_customer_filters",
	"get_chile_rut_customers",
	"normalize_customer_identity",
	"validate_customer_identity",
]


def assert_identity_unique(identity_key, exclude_name=None):
	filters = {"custom_identity_key": identity_key}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]
	existing = frappe.db.get_value("Customer", filters, ["name", "custom_tax_id_type"], as_dict=True)
	if existing:
		frappe.throw(
			frappe._(
				"Ya existe un Customer ({0}) con esta identidad {1}."
			).format(existing.name, existing.custom_tax_id_type or ""),
			frappe.ValidationError,
		)


def apply_customer_identity(doc):
	"""Mutate Customer doc with canonical identity fields. Call from validate."""
	tax_id = (doc.get("tax_id") or "").strip()
	doc_type = (doc.get("custom_tax_id_type") or "").strip()
	country = (doc.get("custom_tax_id_country") or "").strip()

	if not tax_id and not doc_type and not country:
		if doc.is_new():
			frappe.throw(
				frappe._("Tipo de documento y Número de documento / Tax ID son obligatorios."),
				frappe.ValidationError,
			)
		doc.custom_identity_key = None
		return

	if doc.is_new() and not doc_type:
		doc_type = "RUT"
		doc.custom_tax_id_type = "RUT"

	if not tax_id:
		frappe.throw(
			frappe._("Número de documento / Tax ID es obligatorio para una identidad completa."),
			frappe.ValidationError,
		)
	if not doc_type:
		frappe.throw(
			frappe._("Tipo de documento es obligatorio cuando hay Número de documento / Tax ID."),
			frappe.ValidationError,
		)

	try:
		identity = normalize_customer_identity(doc_type, country, tax_id)
	except IdentityValidationError as exc:
		frappe.throw(frappe._(str(exc)), frappe.ValidationError)

	doc.custom_tax_id_type = identity["document_type"]
	doc.custom_tax_id_country = identity["country"]
	doc.tax_id = identity["tax_id"]
	doc.custom_identity_key = identity["identity_key"]
	assert_identity_unique(identity["identity_key"], exclude_name=doc.name)


def validate_customer_identity(doc, method=None):
	apply_customer_identity(doc)


def get_chile_rut_customers(fields=None):
	return frappe.get_all(
		"Customer",
		filters=chile_rut_customer_filters(include_disabled=False),
		fields=fields or ["name", "tax_id"],
	)
