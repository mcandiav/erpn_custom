_REGISTRY = {
	"chilexpress": "erpn_custom.chile.couriers.chilexpress.ChilexpressAdapter",
}


def get_courier_adapter(provider_code):
	code = (provider_code or "").strip().lower()
	path = _REGISTRY.get(code)
	if not path:
		raise ValueError(f"No courier adapter registered for provider {provider_code!r}")
	module_path, class_name = path.rsplit(".", 1)
	module = __import__(module_path, fromlist=[class_name])
	return getattr(module, class_name)()


def registered_providers():
	return sorted(_REGISTRY.keys())
