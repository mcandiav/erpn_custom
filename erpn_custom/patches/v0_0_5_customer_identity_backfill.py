import frappe

from erpn_custom.chile.rut import normalize_chilean_tax_id
from erpn_custom.identity.countries import CHILE
from erpn_custom.identity.service import build_identity_key


def execute():
	rows = frappe.get_all(
		"Customer",
		fields=["name", "tax_id", "custom_tax_id_type", "custom_tax_id_country", "custom_identity_key"],
	)
	summary = {
		"total": len(rows),
		"rut_migrated": 0,
		"legacy_empty": 0,
		"conflicts": 0,
		"already_migrated": 0,
		"duplicate_identity": 0,
		"errors": 0,
	}
	conflicts = []
	pending = []

	for row in rows:
		if row.custom_tax_id_type == "RUT" and row.custom_tax_id_country == CHILE and row.custom_identity_key:
			summary["already_migrated"] += 1
			continue

		tax_id = (row.tax_id or "").strip()
		if not tax_id:
			summary["legacy_empty"] += 1
			continue

		normalized = normalize_chilean_tax_id(tax_id)
		if not normalized:
			summary["conflicts"] += 1
			conflicts.append({"customer": row.name, "reason": "non-RUT legacy value"})
			continue

		pending.append(
			{
				"name": row.name,
				"tax_id": normalized,
				"identity_key": build_identity_key("RUT", CHILE, normalized),
			}
		)

	seen = {}
	winners = []
	for item in pending:
		key = item["identity_key"]
		if key in seen:
			summary["duplicate_identity"] += 1
			conflicts.append(
				{
					"customer": item["name"],
					"reason": "duplicate identity with {0}".format(seen[key]),
				}
			)
			continue
		seen[key] = item["name"]
		winners.append(item)

	for item in winners:
		try:
			frappe.db.set_value(
				"Customer",
				item["name"],
				{
					"tax_id": item["tax_id"],
					"custom_tax_id_type": "RUT",
					"custom_tax_id_country": CHILE,
					"custom_identity_key": item["identity_key"],
				},
				update_modified=False,
			)
			summary["rut_migrated"] += 1
		except Exception:
			summary["errors"] += 1
			conflicts.append({"customer": item["name"], "reason": "patch error"})

	frappe.logger("erpn_custom").info(
		"customer_identity_backfill summary={0}".format(summary)
	)
	if conflicts:
		names = [c["customer"] for c in conflicts[:50]]
		frappe.logger("erpn_custom").warning(
			"customer_identity_backfill conflicts sample={0}".format(names)
		)
