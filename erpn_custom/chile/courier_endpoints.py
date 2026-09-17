import os

_ENV_SLUG = {"Test": "TEST", "Producción": "PROD"}

_SERVICE_KEYS = {
	"coverage": "COVERAGE",
	"rating": "RATING",
	"shipping": "SHIPPING",
}


def endpoint_env_name(provider_code, environment, service):
	code = (provider_code or "").strip().upper()
	env_slug = _ENV_SLUG.get(environment)
	svc = _SERVICE_KEYS.get((service or "").strip().lower())
	if not code or not env_slug or not svc:
		raise ValueError(
			f"Invalid courier endpoint key: provider={provider_code!r} "
			f"environment={environment!r} service={service!r}"
		)
	return f"{code}_{env_slug}_{svc}_URL"


def get_courier_endpoint(provider_code, environment, service):
	"""Resolve endpoint URL from process environment. No HTTP calls."""
	import frappe
	from frappe import _

	var_name = endpoint_env_name(provider_code, environment, service)
	value = (os.environ.get(var_name) or "").strip()
	if not value:
		frappe.throw(_("Missing environment variable: {0}").format(var_name))
	return value
