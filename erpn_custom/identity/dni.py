MAX_DNI_LENGTH = 32


def normalize_dni(country, value):
	"""Generic non-destructive DNI normalization (v1)."""
	if not country:
		return None
	if value is None:
		return None
	raw = str(value).strip()
	if not raw:
		return None
	if len(raw) > MAX_DNI_LENGTH:
		return None
	return raw
