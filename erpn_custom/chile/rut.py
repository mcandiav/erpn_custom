import re

_RUT_BODY = re.compile(r"[^0-9kK]")


def normalize_chilean_tax_id(value):
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    compact = _RUT_BODY.sub("", raw).upper()
    if len(compact) < 2:
        return None
    body, dv = compact[:-1], compact[-1]
    if not body.isdigit():
        return None
    if dv not in "0123456789K":
        return None
    body = str(int(body))
    if not _valid_dv(body, dv):
        return None
    return f"{body}-{dv}"


def _valid_dv(body, dv):
    factors = (2, 3, 4, 5, 6, 7)
    total = 0
    for i, digit in enumerate(reversed(body)):
        total += int(digit) * factors[i % 6]
    rest = 11 - (total % 11)
    if rest == 11:
        expected = "0"
    elif rest == 10:
        expected = "K"
    else:
        expected = str(rest)
    return dv == expected
