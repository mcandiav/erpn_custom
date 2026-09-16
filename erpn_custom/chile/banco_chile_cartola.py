import csv
import io
import unicodedata
from datetime import date, datetime

from erpn_custom.chile.ingest import decide_ingest, make_ingest_key

HEADER_ALIASES = {
	"fecha y hora": "fecha_y_hora",
	"nombre origen": "nombre_origen",
	"nombre o razon social origen": "nombre_origen",
	"rut origen": "rut_origen",
	"banco origen": "banco_origen",
	"cuenta origen": "cuenta_origen",
	"tipo operacion": "tipo_operacion",
	"tipo de operacion": "tipo_operacion",
	"cuenta destino": "cuenta_destino",
	"monto": "monto",
	"id transaccion": "id_transaccion",
	"tipo moneda": "tipo_moneda",
	"tipo operador": "tipo_operador",
	"comentario": "comentario",
}

REQUIRED_CANONICAL = ("fecha_y_hora", "id_transaccion", "monto")
DATE_FORMATS = ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y")
CURRENCY_ALIASES = {"clp": "CLP", "peso": "CLP", "pesos": "CLP", "$": "CLP", "peso chileno": "CLP"}


def fold_header(value):
	text = "" if value is None else str(value).strip()
	if not text:
		return ""
	normalized = unicodedata.normalize("NFKD", text)
	without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
	return " ".join(without_marks.lower().split())


def is_leading_empty_header(value):
	folded = fold_header(value)
	return folded in ("", "unnamed: 0", "column1", "columna a")


def is_banco_chile_headers(headers):
	canonical = set()
	for header in headers:
		key = HEADER_ALIASES.get(fold_header(header))
		if key:
			canonical.add(key)
	return "fecha_y_hora" in canonical and ("id_transaccion" in canonical or "rut_origen" in canonical)


def parse_banco_chile_datetime(value):
	if value in (None, ""):
		return None, None
	if isinstance(value, datetime):
		return value.replace(second=0, microsecond=0) if value.second or value.microsecond else value, value.date()
	if isinstance(value, date) and not isinstance(value, datetime):
		return datetime(value.year, value.month, value.day), value
	text = str(value).strip()
	if not text:
		return None, None
	for fmt in DATE_FORMATS:
		try:
			parsed = datetime.strptime(text, fmt)
			return parsed, parsed.date()
		except ValueError:
			continue
	return None, None


def parse_chilean_amount(value):
	if value in (None, ""):
		return None
	if isinstance(value, bool):
		return None
	if isinstance(value, int | float):
		return float(value)
	raw = str(value).strip().replace("\xa0", " ").replace(" ", "")
	raw = raw.replace("$", "")
	if not raw:
		return None
	negative = raw.startswith("-") or (raw.startswith("(") and raw.endswith(")"))
	raw = raw.strip("()-")
	if not raw:
		return None
	if "," in raw and "." in raw:
		raw = raw.replace(".", "").replace(",", ".")
	elif "," in raw:
		left, right = raw.rsplit(",", 1)
		if right.isdigit() and len(right) <= 2:
			raw = left.replace(".", "") + "." + right
		else:
			raw = raw.replace(",", "")
	elif "." in raw:
		parts = raw.split(".")
		if all(part.isdigit() for part in parts) and all(len(part) == 3 for part in parts[1:]):
			raw = "".join(parts)
	try:
		amount = float(raw)
	except ValueError:
		return None
	return -amount if negative else amount


def normalize_currency(value):
	if value in (None, ""):
		return None
	folded = fold_header(value)
	return CURRENCY_ALIASES.get(folded, str(value).strip().upper())


def drop_leading_empty_columns(row):
	cells = list(row)
	while cells and is_leading_empty_header(cells[0]):
		cells.pop(0)
	return cells


def find_header_row(rows):
	for index, row in enumerate(rows):
		trimmed = drop_leading_empty_columns(row)
		if is_banco_chile_headers(trimmed):
			return index, trimmed
	return None, None


def header_index_map(headers):
	mapping = {}
	for index, header in enumerate(headers):
		canonical = HEADER_ALIASES.get(fold_header(header))
		if canonical and canonical not in mapping:
			mapping[canonical] = index
	return mapping


def cell_at(row, mapping, canonical):
	index = mapping.get(canonical)
	if index is None or index >= len(row):
		return None
	value = row[index]
	if value is None:
		return None
	if isinstance(value, str):
		value = value.strip()
		return value or None
	return value


def parse_cartola_rows(rows):
	header_index, headers = find_header_row(rows)
	if header_index is None:
		return {"ok": False, "reason": "not_banco_chile", "records": []}
	mapping = header_index_map(headers)
	missing = [name for name in REQUIRED_CANONICAL if name not in mapping]
	if missing:
		return {"ok": False, "reason": "missing_columns", "missing": missing, "records": []}

	records = []
	for offset, raw_row in enumerate(rows[header_index + 1 :], start=header_index + 2):
		row = drop_leading_empty_columns(raw_row)
		if not row or all(cell in (None, "") for cell in row):
			continue
		records.append(parse_cartola_row(row, mapping, offset))
	return {"ok": True, "headers": headers, "records": records}


def parse_cartola_row(row, mapping, row_number):
	fecha_raw = cell_at(row, mapping, "fecha_y_hora")
	when, day = parse_banco_chile_datetime(fecha_raw)
	amount = parse_chilean_amount(cell_at(row, mapping, "monto"))
	transaction_id = cell_at(row, mapping, "id_transaccion")
	if transaction_id is not None:
		transaction_id = str(transaction_id).strip()
	error = None
	if not when or not day:
		error = "invalid_datetime"
	elif amount is None or amount == 0:
		error = "invalid_amount"
	elif not (transaction_id or "").strip():
		error = "missing_transaction_id"
	return {
		"row_number": row_number,
		"date": day,
		"custom_fecha_y_hora_bancaria": when,
		"bank_party_name": _as_text(cell_at(row, mapping, "nombre_origen")),
		"custom_rut_del_pagador": _as_text(cell_at(row, mapping, "rut_origen")),
		"custom_banco_origen": _as_text(cell_at(row, mapping, "banco_origen")),
		"bank_party_account_number": _as_text(cell_at(row, mapping, "cuenta_origen")),
		"transaction_type": _as_text(cell_at(row, mapping, "tipo_operacion")),
		"custom_cuenta_destino": _as_text(cell_at(row, mapping, "cuenta_destino")),
		"deposit": amount if amount and amount > 0 else 0,
		"withdrawal": abs(amount) if amount and amount < 0 else 0,
		"transaction_id": (transaction_id or "").strip(),
		"currency": normalize_currency(cell_at(row, mapping, "tipo_moneda")),
		"custom_tipo_operador": _as_text(cell_at(row, mapping, "tipo_operador")),
		"description": _as_text(cell_at(row, mapping, "comentario")),
		"error": error,
	}


def process_cartola_records(records, bank_account, existing_names_for):
	seen = set()
	results = []
	for record in records:
		row_result = {
			"row_number": record["row_number"],
			"transaction_id": record.get("transaction_id") or "",
		}
		if record.get("error"):
			row_result.update({"result": "rejected", "reason": record["error"]})
			results.append(row_result)
			continue
		existing = list(existing_names_for(bank_account, record["transaction_id"]) or [])
		key = make_ingest_key(bank_account, record["transaction_id"])
		if key and key in seen:
			existing = existing or [f"in-file:{record['transaction_id']}"]
		decision = decide_ingest(bank_account, record["transaction_id"], existing)
		if decision == "skip_duplicate":
			row_result.update(
				{
					"result": "skip_duplicate",
					"reason": "duplicate/skipped",
					"existing": existing[0] if existing else None,
				}
			)
		elif decision == "create":
			if key:
				seen.add(key)
			row_result.update({"result": "create", "payload": bank_transaction_payload(record, bank_account)})
		else:
			row_result.update({"result": "rejected", "reason": decision})
		results.append(row_result)
	return results


def bank_transaction_payload(record, bank_account):
	return {
		"doctype": "Bank Transaction",
		"date": record["date"],
		"bank_account": bank_account,
		"status": "Unreconciled",
		"deposit": record["deposit"] or 0,
		"withdrawal": record["withdrawal"] or 0,
		"currency": record["currency"],
		"description": record["description"],
		"transaction_id": record["transaction_id"],
		"transaction_type": record["transaction_type"],
		"bank_party_name": record["bank_party_name"],
		"bank_party_account_number": record["bank_party_account_number"],
		"custom_fecha_y_hora_bancaria": record["custom_fecha_y_hora_bancaria"],
		"custom_rut_del_pagador": record["custom_rut_del_pagador"],
		"custom_banco_origen": record["custom_banco_origen"],
		"custom_cuenta_destino": record["custom_cuenta_destino"],
		"custom_tipo_operador": record["custom_tipo_operador"],
	}


def load_tabular_bytes(content, filename=""):
	name = (filename or "").lower()
	raw = content if isinstance(content, bytes | bytearray) else str(content).encode("utf-8")
	if name.endswith(".xlsx") or raw[:2] == b"PK":
		return _load_xlsx(raw)
	return _load_csv(raw)


def _load_xlsx(raw):
	import openpyxl

	workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
	try:
		sheet = workbook.active
		return [list(row) for row in sheet.iter_rows(values_only=True)]
	finally:
		workbook.close()


def _load_csv(raw):
	text = None
	for encoding in ("utf-8-sig", "cp1252", "latin-1"):
		try:
			text = raw.decode(encoding)
			break
		except UnicodeDecodeError:
			continue
	if text is None:
		text = raw.decode("utf-8", errors="replace")
	sample = text[:4096]
	try:
		dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
	except csv.Error:
		dialect = csv.excel
	return [row for row in csv.reader(io.StringIO(text), dialect)]


def _as_text(value):
	if value in (None, ""):
		return None
	if isinstance(value, datetime):
		return value.strftime("%d-%m-%Y %H:%M")
	text = str(value).strip()
	return text or None
