import re

_NON_DIGIT = re.compile(r"\D")


def normalize_cpf(value):
	"""Normalize Brazilian CPF to 11 digits or return None if invalid."""
	if value is None:
		return None
	digits = _NON_DIGIT.sub("", str(value).strip())
	if len(digits) != 11:
		return None
	if digits == digits[0] * 11:
		return None
	if not _valid_cpf_digits(digits):
		return None
	return digits


def _valid_cpf_digits(digits):
	d1 = _check_digit(digits[:9], range(10, 1, -1))
	d2 = _check_digit(digits[:10], range(11, 1, -1))
	return digits[9] == d1 and digits[10] == d2


def _check_digit(nums, weights):
	total = sum(int(n) * w for n, w in zip(nums, weights))
	rest = total % 11
	return "0" if rest < 2 else str(11 - rest)
