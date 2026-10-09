import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)
sys.modules.setdefault("frappe.utils.file_manager", MagicMock())
sys.modules.setdefault("frappe.custom.doctype.custom_field.custom_field", MagicMock())

from erpn_custom.encargo import barcode_exception as be  # noqa: E402
from erpn_custom.encargo import reception  # noqa: E402


class _Throw(Exception):
	pass


class _PermissionError(Exception):
	pass


def _throw(msg, exc=None, *a, **k):
	raise (exc if isinstance(exc, type) and issubclass(exc, Exception) else _Throw)(msg)


class D(dict):
	__getattr__ = dict.get


SELLER = "vendedor@fra.cl"


def pending_row(**extra):
	row = D(name="ENC-1", status="Open", source_type="KNOWN_ITEM", sales_order="SO-1", expected_item="ITEM-A")
	row.update(extra)
	return row


def pending_event(**extra):
	event = D(
		name="EV-1",
		qty=2,
		status="COMMITTED",
		purchase_barcode="999",
		barcode_exception_status=be.PENDING_APPROVAL,
		expected_barcode="111",
	)
	event.update(extra)
	return event


class BarcodeCase(unittest.TestCase):
	def setUp(self):
		self.frappe = MagicMock()
		self.frappe.throw = _throw
		self.frappe.PermissionError = _PermissionError
		self.frappe.session.user = SELLER
		self.frappe.get_roles.return_value = ["ComercialFRA"]
		for target, name, value in (
			(be, "frappe", self.frappe),
			(be, "_", lambda msg: msg),
			(be, "now_datetime", lambda: "2026-10-07 10:00:00"),
			(be, "responsible_for_order", MagicMock(return_value=(be.SELLER, [SELLER]))),
			(be, "_open_todos", MagicMock()),
			(be, "close_todos", MagicMock()),
			(be, "_audit", MagicMock()),
			(be.inventory, "items_for_barcode", MagicMock(return_value=[])),
			(be.inventory, "add_barcode", MagicMock()),
			(reception, "resume_after_barcode_decision", MagicMock(return_value=[])),
			(be.demand, "locked_events", MagicMock(return_value=[])),
			(be.demand, "reconcile_encargo_supply", MagicMock(return_value=D(pending_supply_qty=2))),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def lock(self, row, *events):
		self.frappe.db.get_value.return_value = row
		be.demand.locked_events.return_value = list(events) if events else [pending_event()]


class TestPureRules(unittest.TestCase):
	def test_match_when_code_is_the_expected_items(self):
		self.assertEqual(be.purchase_outcome("KNOWN_ITEM", "A", ["A"], True), (be.MATCH, False))

	def test_different_code_is_pending_approval(self):
		self.assertEqual(be.purchase_outcome("KNOWN_ITEM", "A", [], True), (be.PENDING_APPROVAL, False))
		self.assertEqual(be.purchase_outcome("KNOWN_ITEM", "A", ["B"], True), (be.PENDING_APPROVAL, False))

	def test_item_without_barcode_adopts_unique_code(self):
		self.assertEqual(be.purchase_outcome("KNOWN_ITEM", "A", [], False), (be.MATCH, True))

	def test_item_without_barcode_but_code_of_other_item_is_pending(self):
		self.assertEqual(be.purchase_outcome("KNOWN_ITEM", "A", ["B"], False), (be.PENDING_APPROVAL, False))

	def test_unknown_item_has_no_barcode_exception(self):
		self.assertEqual(be.purchase_outcome("UNKNOWN_ITEM", None, ["B"], False), ("", False))

	def test_conflict_is_the_other_item(self):
		self.assertEqual(be.approval_conflict("A", ["B"]), "B")
		self.assertIsNone(be.approval_conflict("A", ["A"]))
		self.assertIsNone(be.approval_conflict("A", []))

	def test_responsible_falls_back_by_tier(self):
		tiers = [(be.SELLER, []), (be.OWNER, ["owner@fra.cl"]), (be.ESCALATED, ["sm@fra.cl"])]
		self.assertEqual(be.responsible(tiers), (be.OWNER, ["owner@fra.cl"]))
		self.assertEqual(be.responsible([(be.SELLER, []), (be.ESCALATED, ["sm@fra.cl"])]), (be.ESCALATED, ["sm@fra.cl"]))

	def test_resolution_mode(self):
		self.assertEqual(be.resolution_mode("a", ["ComercialFRA"], ["a"]), "responsible")
		self.assertEqual(be.resolution_mode("sm", ["System Manager"], ["a"]), "override")
		self.assertIsNone(be.resolution_mode("b", ["ComercialFRA"], ["a"]))

	def test_comment_rules(self):
		self.assertFalse(be.comment_required("approve", "responsible"))
		self.assertTrue(be.comment_required("approve", "override"))
		self.assertTrue(be.comment_required("reject", "responsible"))

	def test_pick_pending_event(self):
		first = pending_event(name="EV-1")
		second = pending_event(name="EV-2")
		done = pending_event(name="EV-3", barcode_exception_status=be.APPROVED)
		rejected = pending_event(name="EV-4", status="REJECTED")
		self.assertIs(be.pick_pending_event([first, done]), first)
		self.assertIsNone(be.pick_pending_event([first, second]))
		self.assertIs(be.pick_pending_event([first, second], "EV-2"), second)
		self.assertIsNone(be.pick_pending_event([done, rejected]))
		self.assertIsNone(be.pick_pending_event([first], "EV-3"))

	def test_matches_search(self):
		row = D(name="ENC-1", sales_order="OV-2026-00328", purchase_barcode="191267529486")
		self.assertTrue(be.matches_search(row, ""))
		self.assertTrue(be.matches_search(row, "00328"))
		self.assertTrue(be.matches_search(row, "5294"))
		self.assertFalse(be.matches_search(row, "otro"))

	@patch.object(be, "_", lambda msg: msg)
	def test_rejected_label(self):
		self.assertEqual(be.status_label(be.REJECTED), "Compra rechazada - decide el vendedor")


class TestApprove(BarcodeCase):
	def test_responsible_approves_and_code_is_added(self):
		self.lock(pending_row())
		result = be.approve("ENC-1")
		self.assertEqual(result["barcode_exception_status"], be.APPROVED)
		be.inventory.add_barcode.assert_called_once_with("ITEM-A", "999")
		be.close_todos.assert_called_once_with("ENC-1", be.TODO_EXCEPTION)
		reception.resume_after_barcode_decision.assert_called_once_with("ENC-1", True, "EV-1")
		self.assertEqual(self.frappe.db.set_value.call_args[0][:2], (be.demand.EVENT, "EV-1"))

	def test_only_the_named_purchase_is_resolved(self):
		self.lock(pending_row(), pending_event(name="EV-1"), pending_event(name="EV-2", purchase_barcode="888"))
		with self.assertRaises(_Throw):
			be.approve("ENC-1")
		result = be.approve("ENC-1", supply_event="EV-2")
		self.assertEqual(result["supply_event"], "EV-2")
		be.inventory.add_barcode.assert_called_once_with("ITEM-A", "888")
		be.close_todos.assert_not_called()

	def test_code_of_other_item_blocks_approval(self):
		self.lock(pending_row())
		be.inventory.items_for_barcode.return_value = ["ITEM-B"]
		with self.assertRaises(_Throw):
			be.approve("ENC-1")
		be.inventory.add_barcode.assert_not_called()

	def test_code_already_on_expected_item_is_not_added_again(self):
		self.lock(pending_row())
		be.inventory.items_for_barcode.return_value = ["ITEM-A"]
		be.approve("ENC-1")
		be.inventory.add_barcode.assert_not_called()

	def test_other_commercial_user_cannot_resolve(self):
		self.lock(pending_row())
		self.frappe.session.user = "otro@fra.cl"
		with self.assertRaises(_PermissionError):
			be.approve("ENC-1")

	def test_override_requires_comment(self):
		self.lock(pending_row())
		self.frappe.session.user = "sm@fra.cl"
		self.frappe.get_roles.return_value = ["System Manager"]
		with self.assertRaises(_Throw):
			be.approve("ENC-1")
		be.approve("ENC-1", comment="vendedor de vacaciones")

	def test_not_pending_is_refused(self):
		self.lock(pending_row(), pending_event(barcode_exception_status=be.MATCH))
		with self.assertRaises(_Throw):
			be.approve("ENC-1")


class TestReject(BarcodeCase):
	def test_reject_requires_comment(self):
		self.lock(pending_row())
		with self.assertRaises(_Throw):
			be.reject("ENC-1")

	def test_reject_frees_the_quota_and_notifies_seller(self):
		self.lock(pending_row())
		result = be.reject("ENC-1", comment="no es el modelo")
		self.assertEqual(result["barcode_exception_status"], be.REJECTED)
		self.assertEqual(result["pending_supply_qty"], 2)
		doctype, name, values = self.frappe.db.set_value.call_args[0][:3]
		self.assertEqual((doctype, name), (be.demand.EVENT, "EV-1"))
		self.assertEqual(values["barcode_exception_status"], be.REJECTED)
		self.assertEqual(values["status"], be.demand.REJECTED)
		self.assertEqual(be._open_todos.call_args[0][1], be.TODO_REJECTED)
		reception.resume_after_barcode_decision.assert_called_once_with("ENC-1", False, "EV-1")
		be.demand.reconcile_encargo_supply.assert_called_once_with("ENC-1")


class TestRejectedUnit(unittest.TestCase):
	def test_unit_leaves_the_encargo_and_goes_to_stock(self):
		unit = D(name="RCU-1", encargo="ENC-1", sales_order="SO-1", customer="C", destination="ENCARGO", scanned_code="999")
		unit.update = dict.update.__get__(unit)
		with patch.object(reception, "_log") as log:
			reception.detach_rejected(unit, "vendedor@fra.cl")
		self.assertEqual(unit["rejected_encargo"], "ENC-1")
		self.assertIsNone(unit["encargo"])
		self.assertIsNone(unit["sales_order"])
		self.assertEqual(unit["destination"], reception.STOCK)
		log.assert_called_once_with("ENC-1", "BARCODE_REJECTED", "vendedor@fra.cl", scanned_code="999", notes="RCU-1")


class TestOnPurchase(unittest.TestCase):
	def setUp(self):
		self.frappe = MagicMock()
		self.frappe.db.get_value.return_value = D(source_type="KNOWN_ITEM", expected_item="ITEM-A")
		for target, name, value in (
			(be, "frappe", self.frappe),
			(be, "expected_barcode_text", MagicMock(return_value="111")),
			(be, "open_exception", MagicMock()),
			(be.inventory, "items_for_barcode", MagicMock(return_value=[])),
			(be.inventory, "add_barcode", MagicMock()),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_different_code_opens_the_exception(self):
		self.assertEqual(be.on_purchase("ENC-1", "EV-1", "999"), be.PENDING_APPROVAL)
		be.open_exception.assert_called_once_with("ENC-1", "EV-1")
		be.inventory.add_barcode.assert_not_called()

	def test_matching_code_has_no_exception(self):
		be.inventory.items_for_barcode.return_value = ["ITEM-A"]
		self.assertEqual(be.on_purchase("ENC-1", "EV-1", "111"), be.MATCH)
		be.open_exception.assert_not_called()

	def test_shopper_message_has_no_commercial_data(self):
		message = be.SHOPPER_MESSAGE.lower()
		self.assertIn("pendiente de aprobaci", message)
		for word in ("cliente", "precio", "ov-", "vendedor"):
			self.assertNotIn(word, message)


class TestOpenTodos(unittest.TestCase):
	def test_one_open_todo_per_user(self):
		frappe = MagicMock()
		frappe.db.exists.side_effect = lambda doctype, filters: filters["allocated_to"] == "a@fra.cl"
		with patch.object(be, "frappe", frappe):
			be._open_todos("ENC-1", be.TODO_EXCEPTION, ["a@fra.cl", "b@fra.cl"], "revisar")
		self.assertEqual(frappe.get_doc.call_count, 1)
		self.assertEqual(frappe.get_doc.call_args[0][0]["allocated_to"], "b@fra.cl")


class TestResumeAfterDecision(unittest.TestCase):
	def setUp(self):
		self.frappe = MagicMock()
		self.frappe.session.user = SELLER
		self.frappe.get_all.return_value = ["RCU-1"]
		self.unit = D(name="RCU-1", encargo="ENC-1")
		self.unit.save = MagicMock()
		self.frappe.get_doc.return_value = self.unit
		for name, value in (
			("frappe", self.frappe),
			("administrator_context", MagicMock()),
			("now_datetime", lambda: "2026-10-09 10:00:00"),
			("_advance", MagicMock()),
			("detach_rejected", MagicMock()),
			("unit_result", MagicMock(return_value={"screen": "OK", "message": ""})),
		):
			patcher = patch.object(reception, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)
		patcher = patch.object(reception.demand, "reconcile_encargo_supply", MagicMock())
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_approval_retries_the_same_unit_without_scan(self):
		result = reception.resume_after_barcode_decision("ENC-1", True, "EV-1")
		filters = self.frappe.get_all.call_args[1]["filters"]
		self.assertEqual(filters, {"encargo": "ENC-1", "status": reception.PENDING_BARCODE_APPROVAL, "supply_event": "EV-1"})
		reception.detach_rejected.assert_not_called()
		reception._advance.assert_called_once_with(self.unit)
		self.unit.save.assert_called_once()
		self.assertEqual(result, [{"unit": "RCU-1", "screen": "OK", "message": ""}])
		reception.demand.reconcile_encargo_supply.assert_called_once_with("ENC-1")

	def test_rejection_sends_the_unit_to_stock_or_classification(self):
		reception.resume_after_barcode_decision("ENC-1", False, "EV-1")
		reception.detach_rejected.assert_called_once_with(self.unit, SELLER)
		reception._advance.assert_called_once_with(self.unit)


class TestWaitingUnitsMigration(unittest.TestCase):
	def test_waiting_units_become_pending_approval(self):
		from erpn_custom.patches import v0_0_42_barcode_exception as patch_42

		frappe = MagicMock()
		frappe.db.sql_list.return_value = ["ENC-1", "ENC-2"]
		with patch.object(patch_42, "frappe", frappe):
			patch_42.map_waiting_units()
		query = frappe.db.sql_list.call_args[0][0]
		self.assertIn("PENDING_BARCODE_APPROVAL", query)
		self.assertIn("KNOWN_ITEM", query)
		calls = [c[0][:4] for c in frappe.db.set_value.call_args_list]
		self.assertEqual(
			calls,
			[("Encargo", "ENC-1", "barcode_exception_status", "PENDING_APPROVAL"), ("Encargo", "ENC-2", "barcode_exception_status", "PENDING_APPROVAL")],
		)


if __name__ == "__main__":
	unittest.main()
