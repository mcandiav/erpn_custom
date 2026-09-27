import frappe
from frappe import _

from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS, DEPARTMENTS
from erpn_custom.catalog.seed import aduana_seed, normalize_text

DOCTYPE = "Diccionario Aduana"


def validate_target(tipo, value):
	"""The official ERP value a dictionary entry points to must exist."""
	if tipo == "Tipo":
		ok = frappe.db.exists("Item Group", value)
	elif tipo == "Marca":
		ok = frappe.db.exists("Brand", value)
	elif tipo == "Departamento":
		ok = value in DEPARTMENTS
	elif tipo in ATTRIBUTE_FIELDS:
		ok = frappe.db.exists("Item Attribute Value", {"parent": tipo, "attribute_value": value})
	else:
		ok = False
	if not ok:
		frappe.throw(_("{0} «{1}» no existe en el ERP.").format(_(tipo), value))


def translate(tipo, raw, origen=None):
	"""Official value for a raw source text, or None; unknown texts wait in the queue."""
	texto = normalize_text(raw)
	if not texto:
		return None
	name = f"{tipo}: {texto}"
	entry = frappe.db.get_value(DOCTYPE, name, ["estado", "valor_erp"], as_dict=True)
	if entry:
		frappe.db.sql(
			"update `tabDiccionario Aduana` set ocurrencias = ocurrencias + 1 where name = %s", name
		)
		return entry.valor_erp if entry.estado == "Clasificado" else None
	frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"tipo_dato": tipo,
			"texto": texto,
			"estado": "En espera",
			"origen": origen,
			"ocurrencias": 1,
		}
	).insert(ignore_permissions=True)
	return None


def apply_aduana_seed():
	"""Load the initial aliases; existing entries are left as the Administrator set them."""
	for tipo, text, value in aduana_seed():
		texto = normalize_text(text)
		if frappe.db.exists(DOCTYPE, f"{tipo}: {texto}"):
			continue
		if tipo == "Marca" and not frappe.db.exists("Brand", value):
			continue
		frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"tipo_dato": tipo,
				"texto": texto,
				"estado": "Clasificado",
				"valor_erp": value,
				"origen": "Semilla",
			}
		).insert(ignore_permissions=True)
