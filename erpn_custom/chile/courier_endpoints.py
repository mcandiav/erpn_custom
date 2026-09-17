import frappe
from frappe import _

from erpn_custom.chile.courier_credentials import STANDARD_COURIER_CREDENTIAL_KEYS

_SERVICE_TO_KEY = {
	"coverage": "coverage_api_key",
	"rating": "rating_api_key",
	"shipping": "shipping_api_key",
	"coverage_api_key": "coverage_api_key",
	"rating_api_key": "rating_api_key",
	"shipping_api_key": "shipping_api_key",
}


def _service_key(service):
	key = _SERVICE_TO_KEY.get((service or "").strip().lower()) or _SERVICE_TO_KEY.get(
		(service or "").strip()
	)
	if key not in STANDARD_COURIER_CREDENTIAL_KEYS:
		frappe.throw(_("Invalid courier service: {0}").format(service))
	return key


def _get_configuration(provider_code, environment):
	provider = frappe.db.get_value("Courier Provider", {"provider_code": provider_code}, "name")
	if not provider:
		provider = provider_code
	name = frappe.db.get_value(
		"Courier Configuration",
		{"provider": provider, "environment": environment, "enabled": 1},
		"name",
	)
	if not name:
		frappe.throw(
			_("No enabled Courier Configuration for {0} / {1}").format(provider_code, environment)
		)
	return frappe.get_doc("Courier Configuration", name)


def _get_service_row(provider_code, environment, service):
	key = _service_key(service)
	doc = _get_configuration(provider_code, environment)
	for row in doc.credentials or []:
		if (row.credential_key or "").strip() == key:
			return row
	frappe.throw(
		_("Missing service row {0} on Courier Configuration {1}").format(key, doc.name)
	)


def get_courier_endpoint(provider_code, environment, service):
	"""Resolve endpoint URL from Courier Configuration (Desk). No HTTP calls."""
	row = _get_service_row(provider_code, environment, service)
	url = (row.endpoint_url or "").strip()
	if not url:
		frappe.throw(
			_("Missing endpoint_url for {0} / {1} / {2}").format(
				provider_code, environment, _service_key(service)
			)
		)
	return url


def get_courier_api_key(provider_code, environment, service):
	"""Resolve API key from Courier Configuration Password field. No HTTP calls."""
	row = _get_service_row(provider_code, environment, service)
	secret = row.get_password("secret_value", raise_exception=False)
	if not secret:
		frappe.throw(
			_("Missing API key for {0} / {1} / {2}").format(
				provider_code, environment, _service_key(service)
			)
		)
	return secret
