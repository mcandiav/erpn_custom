STANDARD_COURIER_CREDENTIAL_KEYS = (
	"coverage_api_key",
	"rating_api_key",
	"shipping_api_key",
)

# Operador: Cobertura / Cotizacion / Envio. Adapter traduce al nombre real de cada API.
CREDENTIAL_KEY_LABELS = {
	"coverage_api_key": "Cobertura",
	"rating_api_key": "Cotizacion",
	"shipping_api_key": "Envio",
}


def default_credential_rows():
	return [{"credential_key": key} for key in STANDARD_COURIER_CREDENTIAL_KEYS]
