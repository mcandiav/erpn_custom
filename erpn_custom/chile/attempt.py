import json


def serialize_candidates(names):
    unique = list(dict.fromkeys(names or []))
    return len(unique), json.dumps(unique, ensure_ascii=False)


def conflict_reason(normalized_rut, candidates):
    count, _payload = serialize_candidates(candidates)
    return f"{count} Customers coinciden con RUT {normalized_rut or ''}"
