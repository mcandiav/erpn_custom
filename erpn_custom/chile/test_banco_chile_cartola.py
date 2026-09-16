import unittest
from datetime import date, datetime

from erpn_custom.chile.banco_chile_cartola import (
	is_banco_chile_headers,
	load_tabular_bytes,
	parse_banco_chile_datetime,
	parse_cartola_rows,
	parse_chilean_amount,
	process_cartola_records,
)

HEADERS = [
	"",
	"Fecha y hora",
	"Nombre origen",
	"RUT origen",
	"Banco origen",
	"Cuenta origen",
	"Tipo operación",
	"Cuenta destino",
	"Monto",
	"ID Transacción",
	"Tipo Moneda",
	"Tipo Operador",
	"Comentario",
]

ROW = [
	"",
	"15-08-2026 23:06",
	"Cynthia Contreras Soto",
	"13.698.154-4",
	"Banco de Chile",
	"00123456789",
	"Abono Transferencia",
	"00-123-456",
	"$119.990",
	"TX-CYNTHIA",
	"CLP",
	"Internet",
	"Pago live",
]


class TestBancoChileCartola(unittest.TestCase):
	def test_headers_ignore_empty_column_a(self):
		self.assertTrue(is_banco_chile_headers(HEADERS))

	def test_parse_datetime_banco_chile(self):
		when, day = parse_banco_chile_datetime("15-08-2026 23:06")
		self.assertEqual(when, datetime(2026, 8, 15, 23, 6))
		self.assertEqual(day, date(2026, 8, 15))

	def test_parse_chilean_amount(self):
		self.assertEqual(parse_chilean_amount("$119.990"), 119990.0)
		self.assertEqual(parse_chilean_amount("$1.119.990"), 1119990.0)
		self.assertEqual(parse_chilean_amount("$119.990,50"), 119990.5)
		self.assertEqual(parse_chilean_amount(119990), 119990.0)

	def test_parse_rows_maps_schema_and_ignores_empty_a(self):
		parsed = parse_cartola_rows([HEADERS, ROW])
		self.assertTrue(parsed["ok"])
		record = parsed["records"][0]
		self.assertEqual(record["date"], date(2026, 8, 15))
		self.assertEqual(record["custom_fecha_y_hora_bancaria"], datetime(2026, 8, 15, 23, 6))
		self.assertEqual(record["bank_party_name"], "Cynthia Contreras Soto")
		self.assertEqual(record["custom_rut_del_pagador"], "13.698.154-4")
		self.assertEqual(record["custom_banco_origen"], "Banco de Chile")
		self.assertEqual(record["bank_party_account_number"], "00123456789")
		self.assertEqual(record["transaction_type"], "Abono Transferencia")
		self.assertEqual(record["custom_cuenta_destino"], "00-123-456")
		self.assertEqual(record["deposit"], 119990.0)
		self.assertEqual(record["transaction_id"], "TX-CYNTHIA")
		self.assertEqual(record["currency"], "CLP")
		self.assertEqual(record["custom_tipo_operador"], "Internet")
		self.assertEqual(record["description"], "Pago live")
		self.assertIsNone(record["error"])

	def test_title_rows_before_headers(self):
		rows = [["Cartola Banco de Chile"], [None, None], HEADERS, ROW]
		parsed = parse_cartola_rows(rows)
		self.assertTrue(parsed["ok"])
		self.assertEqual(len(parsed["records"]), 1)

	def test_csv_bytes_with_empty_first_column(self):
		csv_text = (
			";Fecha y hora;Nombre origen;RUT origen;Banco origen;Cuenta origen;"
			"Tipo operación;Cuenta destino;Monto;ID Transacción;Tipo Moneda;Tipo Operador;Comentario\n"
			";15-08-2026 23:06;Cynthia Contreras Soto;13.698.154-4;Banco de Chile;00123456789;"
			"Abono Transferencia;00-123-456;$119.990;TX-CYNTHIA;CLP;Internet;Pago live\n"
		)
		rows = load_tabular_bytes(csv_text.encode("utf-8"), "cartola.csv")
		parsed = parse_cartola_rows(rows)
		self.assertTrue(parsed["ok"])
		self.assertEqual(parsed["records"][0]["transaction_id"], "TX-CYNTHIA")
		self.assertEqual(parsed["records"][0]["deposit"], 119990.0)

	def test_idempotency_skips_existing_and_in_file_duplicates(self):
		parsed = parse_cartola_rows([HEADERS, ROW, ROW])
		account = "Banco de Chile - Banco de Chile"
		existing = {("Banco de Chile - Banco de Chile", "TX-OLD"): ["ACC-BTN-2026-00001"]}

		def lookup(bank_account, transaction_id):
			return existing.get((bank_account, transaction_id), [])

		results = process_cartola_records(parsed["records"], account, lookup)
		self.assertEqual(results[0]["result"], "create")
		self.assertEqual(results[1]["result"], "skip_duplicate")
		self.assertEqual(results[0]["payload"]["bank_account"], account)
		self.assertEqual(results[0]["payload"]["custom_cuenta_destino"], "00-123-456")

		existing[(account, "TX-CYNTHIA")] = ["ACC-BTN-2026-00004"]
		second = process_cartola_records(parsed["records"][:1], account, lookup)
		self.assertEqual(second[0]["result"], "skip_duplicate")
		self.assertEqual(second[0]["existing"], "ACC-BTN-2026-00004")

	def test_official_banco_chile_headers_map_name_and_operation_type(self):
		headers = [
			"",
			"Fecha y hora",
			"Nombre o razón social origen",
			"Rut origen",
			"Banco Origen",
			"Cuenta Origen",
			"Tipo de operación",
			"Cuenta Destino",
			"Monto",
			"ID Transacción",
			"Tipo Moneda",
			"Tipo Operador",
			"Comentario",
		]
		row = [
			"",
			"15-08-2026 23:06",
			"Cynthia Marcela Contreras Soto",
			"13.698.154-4",
			"Mercado Pago",
			"1058926733",
			"Transferencia",
			"2110194503",
			"$129.980",
			"C0875000292654062260815230124",
			"CLP",
			"CCA",
			"Pago live",
		]
		parsed = parse_cartola_rows([headers, row])
		self.assertTrue(parsed["ok"])
		record = parsed["records"][0]
		self.assertEqual(record["bank_party_name"], "Cynthia Marcela Contreras Soto")
		self.assertEqual(record["transaction_type"], "Transferencia")
		self.assertEqual(record["custom_rut_del_pagador"], "13.698.154-4")
		payload = process_cartola_records(
			parsed["records"],
			"Banco de Chile - Banco de Chile",
			lambda *_: [],
		)[0]["payload"]
		self.assertEqual(payload["bank_party_name"], "Cynthia Marcela Contreras Soto")
		self.assertEqual(payload["transaction_type"], "Transferencia")
		self.assertNotIn("party", payload)
		self.assertNotIn("party_type", payload)


if __name__ == "__main__":
	unittest.main()
