MAX_PASSPORT_LENGTH = 32


def normalize_passport(country, value):
	"""Conservative passport normalization (v1): trim only, no universal regex."""
	if not country:
		return None
	if value is None:
		return None
	raw = str(value).strip()
	if not raw:
		return None
	if len(raw) > MAX_PASSPORT_LENGTH:
		return None
	return raw
