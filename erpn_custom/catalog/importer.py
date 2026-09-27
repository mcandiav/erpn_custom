"""Load products from the source spreadsheet through the Diccionario Aduana.

Upload the .xlsx as a private File, then from bench (simulate first):
  bench --site <site> execute erpn_custom.catalog.importer.import_products \
    --kwargs "{'file_url': '/private/files/Libro1.xlsx', 'dry_run': 1, 'limit': 100}"

dry_run keeps only the new Diccionario entries (texts waiting for the Administrator).
"""

import csv
import io

import frappe
from frappe.utils import cint, flt, now_datetime
from openpyxl import load_workbook

from erpn_custom.catalog.aduana import translate
from erpn_custom.catalog.attributes import ATTRIBUTE_FIELDS, DEPARTMENTS
from erpn_custom.catalog.item import family_of
from erpn_custom.catalog.seed import normalize_text

SHEET = "productos"
WAREHOUSE = "Matriz - FRAG"
OPENING_ACCOUNT = "Apertura temporal - FRAG"
UOM = "Unidad"
ORIGEN = "Importación Libro1"
SAMPLE = 30


def import_products(file_url, dry_run=1, limit=100, only_stock=1, cost=None):
	"""Create Items (and a draft opening Stock Reconciliation) from the spreadsheet rows."""
	frappe.only_for("System Manager")
	dry_run, limit, only_stock = cint(dry_run), cint(limit), cint(only_stock)
	rows = _read_rows(file_url)
	if only_stock:
		rows = [row for row in rows if flt(row.get("stock_actual")) > 0]
	if limit:
		rows = rows[:limit]

	ready, problems, existing, seen = [], [], [], set()
	for row in rows:
		code = _text(row.get("codigo"))
		if not code:
			problems.append((row["_fila"], code, "sin código"))
			continue
		if code in seen:
			problems.append((row["_fila"], code, "código repetido en la planilla"))
			continue
		seen.add(code)
		if frappe.db.exists("Item", code):
			existing.append(code)
			continue
		barcode_owner = frappe.db.get_value("Item Barcode", {"barcode": code}, "parent")
		if barcode_owner:
			problems.append((row["_fila"], code, f"código de barras ya usado por {barcode_owner}"))
			continue
		item, missing = _build_item(row, code, cost)
		if missing:
			problems.append((row["_fila"], code, ", ".join(missing)))
		else:
			ready.append((row, item))

	# Texts queued for the Administrator must survive a simulation.
	frappe.db.commit()

	report = {
		"dry_run": bool(dry_run),
		"filas": len(rows),
		"listos": len(ready),
		"incompletos": len(problems),
		"ya_existen": len(existing),
		"muestra_incompletos": [f"fila {f} {c}: {m}" for f, c, m in problems[:SAMPLE]],
		"pendientes_aduana": _pending_counts(),
	}
	if problems:
		report["archivo_incompletos"] = _problems_file(problems)
	if dry_run:
		return report

	created = []
	for row, item in ready:
		frappe.get_doc(item).insert(ignore_permissions=True)
		created.append((item["item_code"], flt(row.get("stock_actual")), item["valuation_rate"]))
	report["creados"] = len(created)
	if created:
		report["inventario_borrador"] = _draft_opening_stock(created)
	frappe.db.commit()
	return report


def _read_rows(file_url):
	path = frappe.get_doc("File", {"file_url": file_url}).get_full_path()
	workbook = load_workbook(filename=path, data_only=True, read_only=True)
	sheet = [list(values) for values in workbook[SHEET].iter_rows(values_only=True)]
	workbook.close()
	header = [normalize_text(_text(h)) for h in sheet[0]]
	rows = []
	for index, values in enumerate(sheet[1:], start=2):
		row = dict(zip(header, values))
		row["_fila"] = index
		rows.append(row)
	return rows


def _build_item(row, code, cost):
	missing, leftovers = [], []

	brand = _resolve("Marca", row.get("marca"), lambda v: frappe.db.get_value("Brand", v, "name"))
	if not brand:
		missing.append(f"marca «{_text(row.get('marca'))}» sin clasificar")
	item_group = _resolve("Tipo", row.get("tipo"), _leaf_group)
	if not item_group:
		missing.append(f"tipo «{_text(row.get('tipo'))}» sin clasificar")
	if missing:
		return None, missing

	item = {
		"doctype": "Item",
		"item_code": code,
		"item_name": (_text(row.get("descripcion")) or code)[:140],
		"item_group": item_group,
		"brand": brand,
		"stock_uom": UOM,
		"is_stock_item": 1,
		"valuation_rate": flt(cost) if cost else flt(row.get("costo")) or 1000,
		"custom_sku_proveedor": _text(row.get("sku")) or None,
		"barcodes": [{"barcode": code}],
	}

	departamento = _resolve("Departamento", row.get("departamento"), _department)
	if departamento:
		item["custom_departamento"] = departamento
	elif _text(row.get("departamento")):
		leftovers.append(f"Departamento: {_text(row.get('departamento'))}")

	family = family_of(item_group)
	for attribute, column in (("Color", "color"), ("Talla", "talla")):
		raw = _text(row.get(column))
		if not raw:
			continue
		value = _resolve(attribute, raw, lambda v, a=attribute: _attribute_value(a, v, family))
		if value:
			item[ATTRIBUTE_FIELDS[attribute]] = value
		else:
			leftovers.append(f"{attribute}: {raw}")

	description = _text(row.get("descripcion"))
	item["description"] = "<br>".join([description, *leftovers]) if leftovers else description
	return item, []


def _resolve(tipo, raw, direct):
	"""Exact official value first; otherwise ask the Diccionario (unknown texts get queued)."""
	raw = _text(raw)
	if not raw:
		return None
	return direct(raw) or translate(tipo, raw, origen=ORIGEN)


def _leaf_group(value):
	name = frappe.db.get_value("Item Group", value, "name")
	if name and not frappe.db.get_value("Item Group", name, "is_group"):
		return name
	return None


def _department(value):
	key = normalize_text(value)
	return next((d for d in DEPARTMENTS if normalize_text(d) == key), None)


def _attribute_value(attribute, value, family):
	row = frappe.db.get_value(
		"Item Attribute Value",
		{"parent": attribute, "attribute_value": value},
		["attribute_value", "custom_familia"],
		as_dict=True,
	)
	if not row or (attribute == "Talla" and row.custom_familia not in (None, "", family)):
		return None
	return row.attribute_value


def _pending_counts():
	rows = frappe.get_all(
		"Diccionario Aduana", filters={"estado": "En espera"}, fields=["tipo_dato"], limit_page_length=0
	)
	counts = {}
	for row in rows:
		counts[row.tipo_dato] = counts.get(row.tipo_dato, 0) + 1
	return counts


def _problems_file(problems):
	buffer = io.StringIO()
	writer = csv.writer(buffer)
	writer.writerow(["fila_excel", "codigo", "problema"])
	writer.writerows(problems)
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"import_incompletos_{now_datetime():%Y%m%d_%H%M%S}.csv",
			"content": buffer.getvalue().encode("utf-8-sig"),
			"is_private": 1,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return file.file_url


def _draft_opening_stock(created):
	company = frappe.db.get_value("Warehouse", WAREHOUSE, "company")
	doc = frappe.get_doc(
		{
			"doctype": "Stock Reconciliation",
			"company": company,
			"purpose": "Opening Stock",
			"expense_account": OPENING_ACCOUNT,
			"items": [
				{"item_code": code, "warehouse": WAREHOUSE, "qty": qty, "valuation_rate": rate}
				for code, qty, rate in created
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _text(value):
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		value = int(value)
	return str(value).strip()
