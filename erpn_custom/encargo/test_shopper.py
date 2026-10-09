import base64
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.validate_and_sanitize_search_inputs = lambda f: f
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


_frappe.throw = _throw
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)
sys.modules.setdefault("frappe.utils.file_manager", MagicMock())

from erpn_custom.encargo import shopper  # noqa: E402

PNG = "data:image/png;base64," + base64.b64encode(b"img").decode()


class TestShopperRules(unittest.TestCase):
	def setUp(self):
		# Other test modules may have installed a different frappe mock first.
		for target, name, value in (
			(shopper.frappe, "throw", _throw),
			(shopper, "_", lambda msg: msg),
			(shopper, "flt", lambda v, *a, **k: float(v or 0)),
			(shopper, "cint", lambda v: int(v or 0)),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_currency_label_never_bare_dollar(self):
		self.assertEqual(shopper.currency_label("USD", "$"), "USD$")
		self.assertEqual(shopper.currency_label("EUR", "€"), "EUR€")
		self.assertEqual(shopper.currency_label("CHF", "CHF"), "CHF")
		self.assertEqual(shopper.currency_label("CLP", "CLP$"), "CLP$")
		self.assertEqual(shopper.currency_label(None, ""), "USD")

	def test_shopper_currency_defaults_to_usd(self):
		with patch.object(shopper.frappe.db, "get_value", return_value=None):
			self.assertEqual(shopper.shopper_currency("a@x.cl"), "USD")
		with patch.object(shopper.frappe.db, "get_value", return_value="EUR"):
			self.assertEqual(shopper.shopper_currency("b@x.cl"), "EUR")

	def test_totals_split_by_currency(self):
		rows = [
			{"purchase_currency": "USD", "purchase_total": 10},
			{"purchase_currency": "EUR", "purchase_total": 5.5},
			{"purchase_currency": "USD", "purchase_total": 2.25},
		]
		totals = shopper.totals_by_currency(rows, {"USD": "USD$", "EUR": "EUR€"})
		self.assertEqual(
			totals,
			[{"currency": "USD", "label": "USD$", "total": 12.25}, {"currency": "EUR", "label": "EUR€", "total": 5.5}],
		)
		self.assertEqual(shopper.totals_by_currency([], {}), [])

	def test_role_gate(self):
		self.assertTrue(shopper.is_shopper(["ShopperFRA", "Guest"]))
		self.assertFalse(shopper.is_shopper(["ComercialFRA", "Sales User"]))

	def test_all_four_evidences_required(self):
		self.assertEqual(shopper.missing_evidence("123", ("x", "jpg"), ("y", "jpg"), 49.99), [])
		missing = shopper.missing_evidence(" ", None, ("y", "jpg"), 0)
		self.assertEqual(missing, ["barcode", "foto del producto", "precio"])

	def test_decode_image(self):
		self.assertEqual(shopper.decode_image(PNG), (b"img", "png"))
		self.assertIsNone(shopper.decode_image("data:text/html;base64,PHA+"))
		self.assertIsNone(shopper.decode_image("data:image/jpeg;base64,***"))
		self.assertIsNone(shopper.decode_image(None))

	def test_pending_is_confirmed(self):
		row = {"status": "Open"}
		self.assertEqual(shopper.purchase_decision(row, [], "s1@x.cl", "REQ-00001", 2, 5), ("confirm", None))

	def test_partial_purchases_until_demand_is_sourced(self):
		row = {"status": "Open"}
		earlier = [{"request_id": "REQ-00001", "shopper_user": "s1@x.cl", "qty": 2}]
		self.assertEqual(shopper.purchase_decision(row, earlier, "s2@x.cl", "REQ-00002", 3, 3), ("confirm", None))
		with self.assertRaises(_Throw):
			shopper.purchase_decision(row, earlier, "s2@x.cl", "REQ-00002", 4, 3)
		with self.assertRaises(_Throw):
			shopper.purchase_decision(row, earlier, "s2@x.cl", "REQ-00003", 1, 0)

	def test_retry_of_same_purchase_is_idempotent(self):
		row = {"status": "Open"}
		previous = {"request_id": "REQ-00001", "shopper_user": "s1@x.cl"}
		self.assertEqual(
			shopper.purchase_decision(row, [previous], "s1@x.cl", "REQ-00001", 1, 0), ("already_done", previous)
		)

	def test_other_shopper_cannot_reuse_request(self):
		row = {"status": "Open"}
		previous = {"request_id": "REQ-00001", "shopper_user": "s1@x.cl"}
		with self.assertRaises(_Throw):
			shopper.purchase_decision(row, [previous], "s2@x.cl", "REQ-00001", 1, 4)

	def test_cancelled_or_draft_not_purchasable(self):
		for status in ("Draft", "Cancelled", "Closed"):
			with self.assertRaises(_Throw):
				shopper.purchase_decision({"status": status}, [], "s1@x.cl", None, 1, 1)

	def test_clean_qty_and_request_id(self):
		self.assertEqual(shopper.clean_qty("3"), 3)
		for bad in (0, -1, 1.5, None):
			with self.assertRaises(_Throw):
				shopper.clean_qty(bad)
		self.assertEqual(shopper.clean_request_id(" 1f2e3d4c-aaaa "), "1f2e3d4c-aaaa")
		self.assertIsNone(shopper.clean_request_id("x"))
		self.assertIsNone(shopper.clean_request_id("drop table;--"))

	def test_review_from_third_not_found(self):
		self.assertFalse(shopper.needs_review(2))
		self.assertTrue(shopper.needs_review(3))
		self.assertTrue(shopper.needs_review(4))

	def test_place_proposed_never_creates_supplier(self):
		with patch.object(shopper.frappe, "db") as db, patch.object(shopper.frappe, "get_doc"):
			self.assertEqual(shopper.resolve_place(None, "  Ross Dress  "), (None, "Ross Dress"))
			self.assertEqual(shopper.resolve_place("TODOS", "Ross"), (None, "Ross"))
			db.exists.assert_not_called()
			shopper.frappe.get_doc.assert_not_called()

	def test_place_master_supplier_wins(self):
		with patch.object(shopper.frappe, "db") as db:
			db.exists.return_value = True
			self.assertEqual(shopper.resolve_place("Macys", "otro"), ("Macys", None))
			db.exists.return_value = False
			with self.assertRaises(_Throw):
				shopper.resolve_place("Inventado", None)

	def test_place_required(self):
		with self.assertRaises(_Throw):
			shopper.resolve_place("TODOS", "  ")

	def test_list_card_hides_commercial_data(self):
		row = MagicMock()
		row.configure_mock(
			name="ENC-2026-00001",
			description="Bota",
			brand="Coach",
			supplier=None,
			custom_talla="US 8 Â· EU 39 Â· CL 38",
			custom_tamano=None,
			size=None,
			reference_image="/private/files/x.png",
			requested_qty=2,
			not_found_count=0,
			needs_commercial_review=0,
			reference_url="https://derp.at-once.cl/desk/sales-order/OV-2026-00003",
		)
		row.get = lambda f, d=None: getattr(row, f, d) if f in ("custom_talla",) else None
		card = shopper._card(row, "derp.at-once.cl")
		self.assertIsNone(card["reference_url"])
		self.assertIsNone(card["reference_text"])
		self.assertNotIn("customer", card)
		self.assertNotIn("sale_rate", card)
		self.assertNotIn("sales_order", card)
		self.assertEqual(card["talla"], "US 8 Â· EU 39 Â· CL 38")
		self.assertIn("shopper.reference_image?encargo=ENC-2026-00001", card["image"])
		self.assertEqual(card["variant"], "Talla: US 8 Â· EU 39 Â· CL 38")

	def test_list_fields_exclude_commercial_data(self):
		for field in ("customer", "sale_rate", "sales_order", "sales_person", "sales_order_item"):
			self.assertNotIn(field, shopper.LIST_FIELDS)
			self.assertNotIn(field, shopper.EVENT_FIELDS)

	def test_reference_link_keeps_store_links(self):
		host = "derp.at-once.cl"
		self.assertEqual(shopper.reference_link("https://www.zara.com/p1", host), ("https://www.zara.com/p1", None))
		self.assertEqual(shopper.reference_link(" www.zara.com/cl/p?x=1 ", host), ("https://www.zara.com/cl/p?x=1", None))
		self.assertEqual(shopper.reference_link("Ver foto en Instagram @tienda", host), (None, "Ver foto en Instagram @tienda"))
		self.assertEqual(shopper.reference_link("", host), (None, None))

	def test_reference_link_drops_erp_links(self):
		host = "derp.at-once.cl"
		for value in (
			"https://derp.at-once.cl/desk/sales-order/OV-2026-00003",
			"HTTPS://DERP.AT-ONCE.CL/app/encargo/ENC-1",
			"derp.at-once.cl/desk/sales-order/OV-2026-00003",
			"/desk/sales-order/OV-2026-00003",
		):
			self.assertEqual(shopper.reference_link(value, host), (None, None), value)

	def test_period_start(self):
		now = datetime(2026, 9, 28, 21, 30, 15)
		self.assertIsNone(shopper.period_start("all", now))
		self.assertEqual(shopper.period_start("7d", now), datetime(2026, 9, 21, 21, 30, 15))
		self.assertEqual(shopper.period_start("today", now), datetime(2026, 9, 28))
		self.assertEqual(shopper.period_start("otro", now), datetime(2026, 9, 28))

	def test_images_of_a_purchase_only_for_its_shopper(self):
		row = {"status": "Open", "pending_supply_qty": 0}
		event = {"shopper_user": "a@x.cl"}
		for kind in ("reference", "product", "label"):
			self.assertTrue(shopper.can_view_image(row, "a@x.cl", kind, event))
			self.assertFalse(shopper.can_view_image(row, "b@x.cl", kind, event))
		self.assertFalse(shopper.can_view_image(row, "a@x.cl", "customer", event))

	def test_pending_encargo_exposes_only_reference(self):
		pending = {"status": "Open", "pending_supply_qty": 2}
		self.assertTrue(shopper.can_view_image(pending, "a@x.cl", "reference"))
		self.assertFalse(shopper.can_view_image(pending, "a@x.cl", "product"))
		self.assertFalse(shopper.can_view_image({**pending, "pending_supply_qty": 0}, "a@x.cl", "reference"))
		self.assertFalse(shopper.can_view_image({**pending, "status": "Cancelled"}, "a@x.cl", "reference"))
		self.assertFalse(shopper.can_view_image(None, "a@x.cl", "reference"))


def _purchase(**over):
	row = {
		"name": "EV1",
		"parent": "ENC-1",
		"idx": 1,
		"source_type": "SHOPPER_PURCHASE",
		"shopper_user": "a@x.cl",
		"status": "COMMITTED",
		"qty": 2,
		"modified": "2026-10-09 12:00:00",
		"purchase_barcode": "111",
		"purchase_price": 10,
		"purchase_currency": "USD",
		"supplier": "Macys",
		"proposed_supplier_name": None,
		"reception_unit": None,
		"barcode_exception_status": "MATCH",
		"purchase_product_image": "/private/files/old-product.jpg",
		"purchase_label_image": "/private/files/old-label.jpg",
	}
	row.update(over)
	return row


class TestPurchaseEdit(unittest.TestCase):
	def setUp(self):
		for target, name, value in (
			(shopper.frappe, "throw", _throw),
			(shopper, "_", lambda msg: msg),
			(shopper, "flt", lambda v, *a, **k: float(v or 0)),
			(shopper, "cint", lambda v: int(v or 0)),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_edit_rules(self):
		self.assertTrue(shopper.purchase_editable("COMMITTED", 0))
		self.assertFalse(shopper.purchase_editable("COMMITTED", 1))
		self.assertFalse(shopper.purchase_editable("RECEIVED", 0))
		self.assertFalse(shopper.purchase_editable("REJECTED", 0))
		self.assertIsNone(shopper.edit_refusal("COMMITTED", 0, False, False))
		self.assertEqual(shopper.edit_refusal("COMMITTED", 1, False, False), shopper.RECEIVED_MESSAGE)
		self.assertEqual(shopper.edit_refusal("RECEIVED", 0, False, False), shopper.RECEIVED_MESSAGE)
		self.assertEqual(shopper.edit_refusal("COMMITTED", 1, False, True), shopper.BARCODE_LINKED_MESSAGE)
		self.assertEqual(shopper.edit_refusal("COMMITTED", 0, True, True), shopper.BARCODE_LINKED_MESSAGE)
		self.assertEqual(shopper.edit_refusal("REJECTED", 0, False, False), shopper.CLOSED_MESSAGE)
		self.assertTrue(shopper.same_revision("2026-10-09 12:00:00.123456", "2026-10-09 12:00:00"))
		self.assertFalse(shopper.same_revision("2026-10-09 12:00:00", "2026-10-09 12:00:01"))
		self.assertFalse(shopper.same_revision(None, "2026-10-09 12:00:00"))
		self.assertEqual(shopper.forbidden_edit_keys(["price", "qty", "purchase_currency"]), ["purchase_currency", "qty"])
		self.assertEqual(shopper.forbidden_edit_keys(["barcode", "supplier"]), [])
		self.assertFalse(shopper._owns_purchase(_purchase(shopper_user="b@x.cl"), "a@x.cl"))
		self.assertTrue(shopper._owns_purchase(_purchase(), "a@x.cl"))
		self.assertFalse(shopper._owns_purchase(None, "a@x.cl"))

	def _run(self, event, seen="2026-10-09 12:00:00", units=None, barcode="111", price=12.5, **kwargs):
		session = MagicMock()
		session.user = "a@x.cl"
		version = MagicMock()
		calls = {"values": None}
		self.calls = calls

		def set_value(doctype, name, values, **kw):
			calls["values"] = dict(values)

		with (
			patch.object(shopper, "_require_shopper"),
			patch.object(shopper, "_form_keys", return_value=[]),
			patch.object(shopper.frappe, "session", session),
			patch.object(shopper.frappe.db, "get_value", return_value=event),
			patch.object(shopper.frappe.db, "set_value", side_effect=set_value),
			patch.object(shopper.frappe.db, "exists", return_value=True),
			patch.object(shopper.frappe, "as_json", side_effect=lambda value: __import__("json").dumps(value)),
			patch.object(shopper.frappe, "get_doc", return_value=version) as get_doc,
			patch.object(shopper.demand, "lock_encargo"),
			patch.object(shopper.demand, "locked_units", return_value=units or []),
			patch.object(shopper.demand, "locked_events", return_value=[]),
			patch.object(shopper.demand, "reconcile_encargo_supply") as reconcile,
			patch.object(shopper.demand, "add_event") as add_event,
			patch.object(shopper.barcode_exception, "on_purchase", return_value="MATCH") as on_purchase,
			patch.object(shopper.barcode_exception, "_close_if_none_pending") as close_todos,
			patch.object(shopper, "_save_evidence", return_value="/private/files/new-product.jpg"),
		):
			result = shopper.update_purchase(
				"EV1",
				modified=seen,
				price=price,
				barcode=barcode,
				supplier=kwargs.get("supplier", "Macys"),
				proposed_supplier_name=kwargs.get("proposed"),
				product_image=kwargs.get("product_image"),
				label_image=kwargs.get("label_image"),
			)
			payload = get_doc.call_args.args[0] if get_doc.called else None
		return result, calls, version, reconcile, add_event, on_purchase, close_todos, payload

	def test_saves_price_without_touching_quantity_or_currency(self):
		result, calls, version, reconcile, add_event, on_purchase, close_todos, payload = self._run(_purchase())
		self.assertEqual(calls["values"], {"purchase_price": 12.5})
		self.assertNotIn("qty", calls["values"])
		self.assertNotIn("purchase_currency", calls["values"])
		self.assertEqual(result["supply_event"], "EV1")
		self.assertNotIn("customer", result)
		self.assertNotIn("sales_order", result)
		add_event.assert_not_called()
		on_purchase.assert_not_called()
		reconcile.assert_not_called()
		close_todos.assert_not_called()
		version.insert.assert_called_once_with(ignore_permissions=True)
		data = __import__("json").loads(payload["data"])
		self.assertEqual(data["row_changed"][0][0], "supply_events")
		self.assertEqual(data["row_changed"][0][2], "EV1")
		self.assertEqual(data["row_changed"][0][3], [["purchase_price", 10, 12.5]])
		self.assertEqual(payload["ref_doctype"], "Encargo")

	def test_other_shopper_and_stale_form_do_not_write(self):
		session = MagicMock()
		session.user = "a@x.cl"
		with (
			patch.object(shopper, "_require_shopper"),
			patch.object(shopper, "_form_keys", return_value=[]),
			patch.object(shopper.frappe, "session", session),
			patch.object(shopper.frappe.db, "get_value", return_value=_purchase(shopper_user="b@x.cl")),
			patch.object(shopper.frappe.db, "set_value") as set_value,
		):
			with self.assertRaises(_Throw) as caught:
				shopper.update_purchase("EV1", modified="2026-10-09 12:00:00", price=9, barcode="111", supplier="Macys")
		self.assertEqual(str(caught.exception), "No autorizado")
		set_value.assert_not_called()

		with (
			patch.object(shopper, "_require_shopper"),
			patch.object(shopper, "_form_keys", return_value=["qty"]),
			patch.object(shopper.frappe.db, "set_value") as set_value,
		):
			with self.assertRaises(_Throw) as caught:
				shopper.update_purchase("EV1", modified="2026-10-09 12:00:00", price=9, barcode="111")
		self.assertEqual(str(caught.exception), shopper.FORBIDDEN_MESSAGE)
		set_value.assert_not_called()

		with self.assertRaises(_Throw) as caught:
			self._run(_purchase(), seen="2026-10-09 11:00:00")
		self.assertEqual(str(caught.exception), shopper.STALE_MESSAGE)
		self.assertIsNone(self.calls["values"])

	def test_received_and_partial_block_the_whole_purchase(self):
		live = [{"supply_event": "EV1", "status": "POSTED", "destination": "ENCARGO"}]
		with self.assertRaises(_Throw) as caught:
			self._run(_purchase(), units=live)
		self.assertEqual(str(caught.exception), shopper.RECEIVED_MESSAGE)
		self.assertIsNone(self.calls["values"])
		with self.assertRaises(_Throw) as caught:
			self._run(_purchase(), units=live, barcode="999")
		self.assertEqual(str(caught.exception), shopper.BARCODE_LINKED_MESSAGE)
		self.assertIsNone(self.calls["values"])
		with self.assertRaises(_Throw) as caught:
			self._run(_purchase(status="REJECTED"))
		self.assertEqual(str(caught.exception), shopper.CLOSED_MESSAGE)
		self.assertIsNone(self.calls["values"])

	def test_barcode_change_reuses_exception_flow_and_keeps_old_photo(self):
		result, calls, version, reconcile, add_event, on_purchase, close_todos, payload = self._run(
			_purchase(barcode_exception_status="PENDING_APPROVAL"),
			barcode="222",
			product_image=PNG,
		)
		self.assertEqual(calls["values"]["purchase_barcode"], "222")
		self.assertEqual(calls["values"]["purchase_product_image"], "/private/files/new-product.jpg")
		self.assertNotIn("purchase_label_image", calls["values"])
		self.assertNotIn("qty", calls["values"])
		self.assertNotIn("purchase_currency", calls["values"])
		on_purchase.assert_called_once_with("ENC-1", "EV1", "222")
		close_todos.assert_called_once()
		reconcile.assert_called_once_with("ENC-1")
		add_event.assert_not_called()
		self.assertEqual(result["supply_event"], "EV1")
		changed = __import__("json").loads(payload["data"])["row_changed"][0][3]
		photos = [row for row in changed if row[0] == "purchase_product_image"]
		self.assertEqual(photos, [["purchase_product_image", "/private/files/old-product.jpg", "/private/files/new-product.jpg"]])
		version.insert.assert_called_once_with(ignore_permissions=True)


if __name__ == "__main__":
	unittest.main()
