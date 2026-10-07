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
	row = D(
		name="ENC-1",
		status="Open",
		source_type="KNOWN_ITEM",
		sales_order="SO-1",
		expected_item="ITEM-A",
		purchase_status="PURCHASED",
		purchase_barcode="999",
		barcode_exception_status=be.PENDING_APPROVAL,
		expected_barcode="111",
	)
	row.update(extra)
	return row


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
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def lock(self, row):
		self.frappe.db.get_value.return_value = row


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
		self.assertTrue(be.comment_required("new_purchase", "responsible"))

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
		reception.resume_after_barcode_decision.assert_called_once_with("ENC-1", approved=True)

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
		self.lock(pending_row(barcode_exception_status=be.MATCH))
		with self.assertRaises(_Throw):
			be.approve("ENC-1")


class TestReject(BarcodeCase):
	def test_reject_requires_comment(self):
		self.lock(pending_row())
		with self.assertRaises(_Throw):
			be.reject("ENC-1")

	def test_reject_keeps_purchase_and_notifies_seller(self):
		self.lock(pending_row())
		result = be.reject("ENC-1", comment="no es el modelo")
		self.assertEqual(result["barcode_exception_status"], be.REJECTED)
		values = self.frappe.db.set_value.call_args[0][2]
		self.assertEqual(values["barcode_exception_status"], be.REJECTED)
		self.assertNotIn("purchase_status", values)
		self.assertEqual(be._open_todos.call_args[0][1], be.TODO_REJECTED)
		reception.resume_after_barcode_decision.assert_called_once_with("ENC-1", approved=False)


class TestNewPurchase(BarcodeCase):
	def test_archives_and_returns_to_pending(self):
		self.lock(pending_row(barcode_exception_status=be.REJECTED))
		attempt = MagicMock()
		self.frappe.get_doc.return_value = attempt
		self.frappe.db.count.return_value = 0
		result = be.request_new_purchase("ENC-1", comment="comprar el correcto")
		self.assertEqual(result["purchase_status"], "PENDING")
		attempt.db_insert.assert_called_once()
		archived = self.frappe.get_doc.call_args[0][0]
		self.assertEqual(archived["result"], "BARCODE_REJECTED")
		self.assertEqual(archived["purchase_barcode"], "999")
		self.frappe.db.set_value.assert_called_with("Encargo", "ENC-1", be.CLEARED_PURCHASE, update_modified=True)

	def test_requires_comment(self):
		self.lock(pending_row(barcode_exception_status=be.REJECTED))
		with self.assertRaises(_Throw):
			be.request_new_purchase("ENC-1")

	def test_only_from_rejected(self):
		self.lock(pending_row())
		with self.assertRaises(_Throw):
			be.request_new_purchase("ENC-1", comment="x")


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


if __name__ == "__main__":
	unittest.main()
