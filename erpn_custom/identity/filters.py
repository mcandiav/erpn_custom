from erpn_custom.identity.countries import CHILE


def chile_rut_customer_filters(include_disabled=False):
	filters = {
		"custom_tax_id_type": "RUT",
		"custom_tax_id_country": CHILE,
	}
	if not include_disabled:
		filters["disabled"] = 0
	return filters
