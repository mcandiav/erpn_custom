NO_MATCH = "No Match"
CONFLICT = "Conflict"
EXACT_TAX_ID = "Exact Tax ID"


def index_customers_by_normalized_tax_id(customers, normalize):
    indexed = {}
    for customer in customers:
        key = normalize(customer.get("tax_id"))
        if not key:
            continue
        indexed.setdefault(key, []).append(customer["name"])
    return indexed


def classify_rut(normalized_rut, customers_by_rut):
    if not normalized_rut:
        return NO_MATCH, []
    names = customers_by_rut.get(normalized_rut) or []
    unique = list(dict.fromkeys(names))
    if len(unique) == 1:
        return EXACT_TAX_ID, unique
    if not unique:
        return NO_MATCH, []
    return CONFLICT, unique
