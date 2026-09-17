import frappe


def execute():
	"""Enable composite uniqueness and retire global tax_id unique."""
	dupes = frappe.db.sql(
		"""
		SELECT custom_identity_key, COUNT(*) AS cnt
		FROM `tabCustomer`
		WHERE IFNULL(custom_identity_key, '') != ''
		GROUP BY custom_identity_key
		HAVING COUNT(*) > 1
		LIMIT 20
		""",
		as_dict=True,
	)
	if dupes:
		frappe.throw(
			"No se puede activar unicidad compuesta: hay identity_key duplicados. "
			"Resuelva conflictos de migración antes de continuar. Sample: {0}".format(
				[d.custom_identity_key for d in dupes]
			)
		)

	_ensure_property_setter(
		doctype="Customer",
		fieldname="tax_id",
		property="unique",
		value="0",
		property_type="Check",
	)
	_ensure_property_setter(
		doctype="Customer",
		fieldname="custom_identity_key",
		property="unique",
		value="1",
		property_type="Check",
	)

	if frappe.db.exists("Custom Field", {"dt": "Customer", "fieldname": "custom_identity_key"}):
		frappe.db.set_value(
			"Custom Field",
			{"dt": "Customer", "fieldname": "custom_identity_key"},
			"unique",
			1,
		)

	frappe.db.sql(
		"UPDATE `tabCustomer` SET custom_identity_key = NULL WHERE IFNULL(custom_identity_key, '') = ''"
	)

	indexes = frappe.db.sql("SHOW INDEX FROM `tabCustomer` WHERE Column_name = 'tax_id'", as_dict=True)
	for idx in indexes:
		if not idx.get("Non_unique"):
			try:
				frappe.db.sql_ddl("ALTER TABLE `tabCustomer` DROP INDEX `{0}`".format(idx.Key_name))
			except Exception:
				frappe.logger("erpn_custom").warning(
					"could not drop tax_id unique index {0}".format(idx.Key_name)
				)

	# Ensure unique index on identity key (empty keys allowed multiple times via NULL-like empty).
	try:
		frappe.db.sql_ddl(
			"ALTER TABLE `tabCustomer` ADD UNIQUE INDEX `unique_custom_identity_key` (`custom_identity_key`)"
		)
	except Exception:
		# Index may already exist after re-run.
		pass


def _ensure_property_setter(doctype, fieldname, property, value, property_type):
	name = f"{doctype}-{fieldname}-{property}"
	if frappe.db.exists("Property Setter", name):
		doc = frappe.get_doc("Property Setter", name)
		doc.value = value
		doc.property_type = property_type
		doc.save(ignore_permissions=True)
		return
	frappe.get_doc(
		{
			"doctype": "Property Setter",
			"doctype_or_field": "DocField",
			"doc_type": doctype,
			"field_name": fieldname,
			"property": property,
			"value": value,
			"property_type": property_type,
			"name": name,
		}
	).insert(ignore_permissions=True)
