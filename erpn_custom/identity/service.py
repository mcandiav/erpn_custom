from erpn_custom.chile.rut import normalize_chilean_tax_id
from erpn_custom.identity.countries import BRAZIL, CHILE
from erpn_custom.identity.cpf import normalize_cpf
from erpn_custom.identity.dni import normalize_dni
from erpn_custom.identity.passport import normalize_passport

ALLOWED_TYPES = ("RUT", "DNI", "CPF", "Passport")


class IdentityValidationError(ValueError):
	"""Domain validation error for Customer identity (no Frappe dependency)."""


def build_identity_key(document_type, country, tax_id):
	return f"{document_type}|{country}|{tax_id}"


def normalize_customer_identity(document_type, country, tax_id):
	"""Normalize and validate Customer identity. Raises IdentityValidationError."""
	doc_type = (document_type or "").strip()
	if doc_type not in ALLOWED_TYPES:
		raise IdentityValidationError("Tipo de documento inválido. Use RUT, DNI, CPF o Passport.")

	country_name = (country or "").strip() or None
	raw_tax_id = tax_id

	if doc_type == "RUT":
		country_name = CHILE
		normalized = normalize_chilean_tax_id(raw_tax_id)
		if not normalized:
			raise IdentityValidationError(
				"RUT inválido: el formato o el dígito verificador no corresponden."
			)
	elif doc_type == "CPF":
		country_name = BRAZIL
		normalized = normalize_cpf(raw_tax_id)
		if not normalized:
			raise IdentityValidationError(
				"CPF inválido: el número no cumple el algoritmo brasileño."
			)
	elif doc_type == "DNI":
		if not country_name:
			raise IdentityValidationError("País emisor es obligatorio para DNI.")
		normalized = normalize_dni(country_name, raw_tax_id)
		if not normalized:
			raise IdentityValidationError(
				"DNI inválido: el número está vacío o excede la longitud permitida."
			)
	else:  # Passport
		if not country_name:
			raise IdentityValidationError("País emisor es obligatorio para Passport.")
		normalized = normalize_passport(country_name, raw_tax_id)
		if not normalized:
			raise IdentityValidationError(
				"Passport inválido: el número está vacío o excede la longitud permitida."
			)

	return {
		"document_type": doc_type,
		"country": country_name,
		"tax_id": normalized,
		"identity_key": build_identity_key(doc_type, country_name, normalized),
	}
