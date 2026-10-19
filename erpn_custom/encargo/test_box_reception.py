import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: int(v or 0)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.encargo import box_reception as box  # noqa: E402
from erpn_custom.encargo import inventory, reception  # noqa: E402

NOW = datetime(2026, 10, 15, 10, 0)
SCAN_ID = "0b7c6f0e-3c1a-4c55-9d7a-1f2e3d4c5b6a"
QR = "https://qrgo.page.link/JsDVr"


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


class D(dict):
	__getattr__ = dict.get

	def __setattr__(self, key, value):
		self[key] = value


def head(status=box.DRAFT, **values):
	row = D(name="BOX-2026-00001", status=status, opened_by="r1@fragallardo.com", job_heartbeat=NOW)
	row.update(values)
	return row


def line(status=box.ACTIVE, **values):
	row = D(
		name="L1",
		box="BOX-2026-00001",
		ordinal=1,
		status=status,
		scanned_code=QR,
		scan_event_id=SCAN_ID,
		scanned_on=NOW,
		scanned_by="r1@fragallardo.com",
		attempts=0,
	)
	row.update(values)
	return row


class BoxCase(unittest.TestCase):
	def setUp(self):
		self.frappe = MagicMock()
		self.frappe.throw = _throw
		self.frappe.get_roles = lambda: ["FRAreceptor"]
		self.frappe.session = D(user="r1@fragallardo.com")
		self.frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
		self.frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
		self.db = self.frappe.db
		for target, name, value in (
			(box, "frappe", self.frappe),
			(box, "_", lambda msg: msg),
			(box, "cint", lambda v: int(v or 0)),
			(box, "now_datetime", lambda: NOW),
			(box, "get_datetime", lambda v: v),
			(reception, "frappe", self.frappe),
			(reception, "_", lambda msg: msg),
		):
			patcher = patch.object(target, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def as_role(self, role):
		self.frappe.get_roles = lambda: [role]


class TestRules(BoxCase):
	def test_pending_lines_skip_consumed_discarded_and_exhausted(self):
		lines = [
			line(name="a"),
			line(name="b", status=box.PROCESSED),
			line(name="c", status=box.DISCARDED),
			line(name="d", status=box.ERROR, attempts=1),
			line(name="e", status=box.ERROR, attempts=box.MAX_AUTO_ATTEMPTS),
		]
		self.assertEqual([row.name for row in box.pending_lines(lines)], ["a", "d"])

	def test_final_status(self):
		posted = D(status=reception.POSTED)
		pending = D(status=reception.PENDING_CLASSIFICATION)
		returned = D(status=reception.RETURNED)
		link_error = D(status=reception.POSTED, materialization_status="ERROR")
		self.assertIsNone(box.final_status([line(), line(status=box.PROCESSED)], [posted]))
		self.assertIsNone(box.final_status([line(status=box.ERROR, attempts=9)], [posted]))
		done = [line(status=box.PROCESSED), line(status=box.DISCARDED)]
		self.assertEqual(box.final_status(done, [posted, returned]), box.FINALIZED)
		self.assertEqual(box.final_status(done, [posted, pending]), box.FINALIZED_WITH_EXCEPTIONS)
		self.assertEqual(box.final_status(done, [link_error]), box.FINALIZED_WITH_EXCEPTIONS)

	def test_totals(self):
		lines = [line(), line(status=box.DISCARDED), line(status=box.PROCESSED), line(status=box.ERROR)]
		totals = box.line_totals(lines, [D(status=reception.PENDING_COST), D(status=reception.POSTED)])
		self.assertEqual(
			totals,
			{"active_lines": 3, "discarded_lines": 1, "processed_lines": 1, "error_lines": 1, "exception_lines": 1},
		)

	def test_stale_and_repeat_and_exact_code(self):
		self.assertTrue(box.is_stale(None, NOW))
		self.assertTrue(box.is_stale(NOW - timedelta(minutes=box.STALE_MINUTES), NOW))
		self.assertFalse(box.is_stale(NOW - timedelta(minutes=1), NOW))
		self.assertTrue(box.repeats_previous("111", "111"))
		self.assertFalse(box.repeats_previous(None, "111"))
		self.assertFalse(box.repeats_previous("111", "112"))
		self.assertEqual(box.exact_codes(["abc", "ABC"], {"abc"}), {"abc"})
		self.assertEqual(box.clean_external_ref("  X" * 100)[:3], "X  ")
		self.assertEqual(len(box.clean_external_ref("Y" * 500)), box.EXTERNAL_REF_MAX)


class TestPreview(BoxCase):
	def test_encargo_preview_is_read_only_and_explicit(self):
		self.db.get_value = MagicMock(return_value=D(name="ENC-2026-00405", customer="Cliente", sales_order="OV-1"))
		with patch.object(inventory, "items_for_barcode", return_value=["ITEM-1"]), patch.object(
			reception, "_candidates", return_value=[D(name="ENC-2026-00405")]
		):
			result = box.preview_for(QR)
		self.assertEqual(
			result,
			{
				"destination": reception.ENCARGO,
				"encargo": "ENC-2026-00405",
				"screen": "APARTAR - ENC-2026-00405",
				"detail": "Cliente · OV-1",
			},
		)
		self.db.set_value.assert_not_called()

	def test_item_preview_reports_stock_without_writes(self):
		self.db.get_value = MagicMock(return_value="Producto")
		with patch.object(inventory, "items_for_barcode", return_value=["ITEM-1"]), patch.object(
			reception, "_candidates", return_value=[]
		):
			result = box.preview_for(QR)
		self.assertEqual(
			(result["destination"], result["screen"], result["detail"]),
			(reception.STOCK, "STOCK NORMAL", "ITEM-1 · Producto"),
		)
		self.db.set_value.assert_not_called()

	def test_unknown_preview_defers_the_decision(self):
		with patch.object(inventory, "items_for_barcode", return_value=[]), patch.object(
			reception, "_candidates", return_value=[]
		):
			result = box.preview_for(QR)
		self.assertEqual((result["destination"], result["screen"]), ("UNRESOLVED", "SIN COINCIDENCIA"))


class TestPermissions(BoxCase):
	ENDPOINTS = {
		"open_box": lambda: box.open_box(),
		"add_line": lambda: box.add_line("BOX-2026-00001", QR, SCAN_ID),
		"discard_line": lambda: box.discard_line("BOX-2026-00001", "L1"),
		"cancel_box": lambda: box.cancel_box("BOX-2026-00001"),
		"finalize_box": lambda: box.finalize_box("BOX-2026-00001"),
		"retry_box": lambda: box.retry_box("BOX-2026-00001"),
		"list_incidents": lambda: box.list_incidents(),
		"get_box": lambda: box.get_box("BOX-2026-00001"),
		"list_boxes": lambda: box.list_boxes(),
	}
	DENIED = {
		"FRAreceptor": ("retry_box", "list_incidents"),
		"ComercialFRA": ("open_box", "add_line", "discard_line", "cancel_box", "finalize_box"),
		"ShopperFRA": tuple(ENDPOINTS),
		"Sales User": tuple(ENDPOINTS),
	}

	def test_each_role_is_denied_outside_its_job(self):
		"""§23.6 #9: outside the authorized role nobody touches a box nor posts stock."""
		for role, endpoints in self.DENIED.items():
			self.as_role(role)
			for endpoint in endpoints:
				with self.subTest(role=role, endpoint=endpoint), self.assertRaises(_Throw):
					self.ENDPOINTS[endpoint]()
		self.frappe.get_doc.assert_not_called()
		self.db.set_value.assert_not_called()
		self.frappe.enqueue.assert_not_called()


class TestDraft(BoxCase):
	def setUp(self):
		super().setUp()
		self.head = head()
		self.db.get_value = MagicMock(side_effect=self.get_value)
		self.existing = None
		self.frappe.get_all = MagicMock(return_value=[])
		for name, value in (
			(
				"preview_for",
				lambda code: {
					"destination": reception.ENCARGO,
					"encargo": "ENC-1",
					"screen": "APARTAR - ENC-1",
					"detail": "Cliente · OV-1",
				},
			),
			("box_detail", lambda name: {"name": name}),
			("_update_counts", MagicMock()),
		):
			patcher = patch.object(box, name, value)
			patcher.start()
			self.addCleanup(patcher.stop)

	def get_value(self, doctype, name, fields=None, *a, **k):
		if doctype == box.BOX:
			return self.head
		if doctype == box.LINE and isinstance(name, dict):
			return self.existing
		if doctype == box.LINE:
			return self.line
		return None

	def test_reads_only_store_lines(self):
		"""§23.6 #1: three reads of the same code, no Stock Entry, Encargo or event before Finalizar."""
		docs = []
		self.frappe.get_doc = lambda payload: docs.append(payload) or MagicMock(as_dict=lambda: D(payload))
		with patch.object(reception, "process_scan") as process, patch.object(
			inventory, "make_receipt"
		) as receipt, patch.object(reception.demand, "add_event") as event:
			for i in range(3):
				box.add_line("BOX-2026-00001", QR, f"{SCAN_ID[:-1]}{i}")
		self.assertEqual([d["scanned_code"] for d in docs], [QR, QR, QR])
		self.assertEqual({d["status"] for d in docs}, {box.ACTIVE})
		self.assertEqual({d["box"] for d in docs}, {"BOX-2026-00001"})
		self.assertEqual({d["preview_destination"] for d in docs}, {reception.ENCARGO})
		self.assertEqual({d["preview_encargo"] for d in docs}, {"ENC-1"})
		process.assert_not_called()
		receipt.assert_not_called()
		event.assert_not_called()
		self.db.set_value.assert_not_called()

	def test_open_box_does_not_require_an_external_label(self):
		"""§23.6 #12: the carrier label is optional and opening a box creates no Shopper task."""
		doc = MagicMock()
		doc.name = "BOX-2026-00002"
		self.frappe.get_doc = MagicMock(return_value=doc)
		result = box.open_box()
		payload = self.frappe.get_doc.call_args.args[0]
		self.assertEqual((payload["doctype"], payload["external_ref"], result["name"]), (box.BOX, "", "BOX-2026-00002"))
		self.frappe.get_doc.assert_called_once()
		doc.insert.assert_called_once_with(ignore_permissions=True)
		self.frappe.enqueue.assert_not_called()

	def test_repeated_read_id_is_not_a_second_line(self):
		"""§23.6 #4: the same scan_event_id answers DUPLICADO without locking or inserting."""
		self.existing = line()
		result = box.add_line("BOX-2026-00001", QR, SCAN_ID)
		self.assertEqual((result["name"], result["duplicate"]), ("L1", 1))
		self.frappe.get_doc.assert_not_called()

	def test_consecutive_same_code_is_only_a_warning(self):
		self.frappe.get_all = MagicMock(side_effect=[[D(ordinal=4)], [D(scanned_code=QR)]])
		self.frappe.get_doc = lambda payload: MagicMock(as_dict=lambda: D(payload))
		result = box.add_line("BOX-2026-00001", QR, SCAN_ID)
		self.assertEqual((result["ordinal"], result["repeated"], result["status"]), (5, 1, box.ACTIVE))

	def test_shift_change_records_who_scanned(self):
		"""§23.8 #4: another receptor continues the box; each read keeps its author."""
		self.frappe.session = D(user="r2@fragallardo.com")
		self.frappe.get_doc = lambda payload: MagicMock(as_dict=lambda: D(payload))
		result = box.add_line("BOX-2026-00001", QR, SCAN_ID)
		self.assertEqual((result["scanned_by"], self.head.opened_by), ("r2@fragallardo.com", "r1@fragallardo.com"))

	def test_closed_box_rejects_reads_and_discards(self):
		"""§23.6 #8."""
		for status in (box.FINALIZING, box.FINALIZED, box.FINALIZED_WITH_EXCEPTIONS, box.CANCELLED):
			self.head = head(status)
			with self.subTest(status=status):
				with self.assertRaises(_Throw):
					box.add_line("BOX-2026-00001", QR, SCAN_ID)
				with self.assertRaises(_Throw):
					box.discard_line("BOX-2026-00001", "L1")
		self.frappe.get_doc.assert_not_called()
		self.db.set_value.assert_not_called()

	def test_discard_keeps_an_audited_line(self):
		"""§23.6 #2: no reason, no reversal; the line stays DISCARDED with user and date."""
		self.line = line()
		result = box.discard_line("BOX-2026-00001", "L1")
		self.db.set_value.assert_called_once_with(
			box.LINE,
			"L1",
			{"status": box.DISCARDED, "discarded_on": NOW, "discarded_by": "r1@fragallardo.com"},
			update_modified=False,
		)
		self.assertEqual(result["status"], box.DISCARDED)
		self.line = line(box="BOX-OTHER")
		with self.assertRaises(_Throw):
			box.discard_line("BOX-2026-00001", "L1")

	def test_cancel_empty_or_with_reads(self):
		"""§23.8 #1."""
		for lines in (0, 3):
			self.db.set_value.reset_mock()
			self.head = head(active_lines=lines)
			box.cancel_box("BOX-2026-00001")
			values = self.db.set_value.call_args.args[2]
			self.assertEqual((values["status"], values["cancelled_by"]), (box.CANCELLED, "r1@fragallardo.com"))
		self.db.set_value.reset_mock()
		self.head = head(box.CANCELLED)
		box.cancel_box("BOX-2026-00001")
		self.db.set_value.assert_not_called()
		self.head = head(box.FINALIZED)
		with self.assertRaises(_Throw):
			box.cancel_box("BOX-2026-00001")
		self.frappe.enqueue.assert_not_called()

	def test_finalize_needs_active_reads_and_queues_once(self):
		self.db.count = MagicMock(return_value=0)
		with self.assertRaises(_Throw):
			box.finalize_box("BOX-2026-00001")
		self.db.count = MagicMock(return_value=2)
		box.finalize_box("BOX-2026-00001")
		values = self.db.set_value.call_args.args[2]
		self.assertEqual((values["status"], values["finalize_requested_by"]), (box.FINALIZING, "r1@fragallardo.com"))
		kwargs = self.frappe.enqueue.call_args.kwargs
		self.assertEqual((kwargs["box"], kwargs["job_id"], kwargs["deduplicate"]), ("BOX-2026-00001", "erpn_custom:box_close:BOX-2026-00001", True))
		# §23.6 #4: pressing Finalizar again does not queue a second close.
		self.frappe.enqueue.reset_mock()
		for status in (box.FINALIZING, box.FINALIZED):
			self.head = head(status)
			box.finalize_box("BOX-2026-00001")
		self.frappe.enqueue.assert_not_called()


class TestCloseJob(BoxCase):
	def setUp(self):
		super().setUp()
		self.line = line()
		self.box_status = box.FINALIZING
		self.db.get_value = MagicMock(side_effect=self.get_value)

	def get_value(self, doctype, name, fields=None, *a, **k):
		if doctype == box.BOX:
			return self.box_status
		return self.line

	def test_line_runs_the_one_unit_service_with_its_own_id(self):
		"""§23.6 #5: the unit keeps BOX and line; the read id becomes the unit id."""
		with patch.object(reception, "process_scan", return_value={"unit": "RCU-1"}) as process:
			box.process_line("L1")
		process.assert_called_once_with(QR, SCAN_ID, "r1@fragallardo.com", NOW, box="BOX-2026-00001", box_line="L1")
		self.db.set_value.assert_any_call(
			box.LINE,
			"L1",
			{"status": box.PROCESSED, "reception_unit": "RCU-1", "processed_on": NOW, "error_message": None},
			update_modified=False,
		)
		self.db.commit.assert_called_once()
		self.db.rollback.assert_not_called()

	def test_consumed_line_is_never_processed_again(self):
		"""§23.6 #4 / #11: a repeated or resumed close skips consumed and discarded lines."""
		with patch.object(reception, "process_scan") as process:
			for status in (box.PROCESSED, box.DISCARDED):
				self.line = line(status)
				box.process_line("L1")
			self.line = line()
			self.box_status = box.CANCELLED
			box.process_line("L1")
		process.assert_not_called()
		self.db.set_value.assert_not_called()

	def test_technical_failure_rolls_back_only_this_unit(self):
		"""§23.6 #11: no orphan movement; the line stays retryable with its attempt counted."""
		self.frappe.get_traceback = lambda: "Deadlock found"
		with patch.object(reception, "process_scan", side_effect=Exception("Deadlock found")):
			box.process_line("L1")
		self.db.rollback.assert_called_once_with()
		values = self.db.set_value.call_args_list[0].args[2]
		self.assertEqual((values["status"], values["attempts"]), (box.ERROR, 1))
		self.db.commit.assert_called_once()

	def test_job_only_runs_on_finalizing_boxes(self):
		self.box_status = box.DRAFT
		with patch.object(box, "process_line") as process, patch.object(box, "finish_box") as finish:
			box.run_box_close("BOX-2026-00001")
		process.assert_not_called()
		finish.assert_not_called()

	def test_job_processes_pending_lines_in_order_then_finishes(self):
		lines = [line(name="L1"), line(name="L2", status=box.PROCESSED), line(name="L3", status=box.ERROR, attempts=1)]
		with patch.object(box, "_lines", return_value=lines), patch.object(box, "process_line") as process, patch.object(
			box, "finish_box"
		) as finish:
			box.run_box_close("BOX-2026-00001")
		self.assertEqual([c.args[0] for c in process.call_args_list], ["L1", "L3"])
		finish.assert_called_once_with("BOX-2026-00001")

	def test_finish_sets_the_final_status(self):
		self.db.get_value = MagicMock(return_value=head(box.FINALIZING))
		with patch.object(box, "_lines", return_value=[line(status=box.PROCESSED)]), patch.object(
			box, "_box_units", return_value=[D(status=reception.PENDING_CLASSIFICATION)]
		):
			self.assertEqual(box.finish_box("BOX-2026-00001"), box.FINALIZED_WITH_EXCEPTIONS)
		values = self.db.set_value.call_args.args[2]
		self.assertEqual((values["status"], values["exception_lines"]), (box.FINALIZED_WITH_EXCEPTIONS, 1))
		self.db.set_value.reset_mock()
		with patch.object(box, "_lines", return_value=[line(status=box.ERROR, attempts=3)]), patch.object(
			box, "_box_units", return_value=[]
		):
			self.assertEqual(box.finish_box("BOX-2026-00001"), box.FINALIZING)
		self.assertNotIn("status", self.db.set_value.call_args.args[2])

	def test_resolved_exception_completes_the_box(self):
		self.db.get_value = MagicMock(return_value=box.FINALIZED_WITH_EXCEPTIONS)
		with patch.object(box, "_box_units", return_value=[D(status=reception.POSTED)]):
			box.refresh_finished_box("BOX-2026-00001")
		self.assertEqual(self.db.set_value.call_args.args[2]["status"], box.FINALIZED)
		self.db.set_value.reset_mock()
		self.db.get_value = MagicMock(return_value=box.FINALIZING)
		box.refresh_finished_box("BOX-2026-00001")
		self.db.set_value.assert_not_called()

	def test_partial_exception_resolves_without_rescanning(self):
		"""§23.6 #6: valid units finish and a pending unit is resolved later without another scan."""
		self.db.get_value = MagicMock(return_value=head(box.FINALIZING))
		processed = [line(name="L1", status=box.PROCESSED), line(name="L2", status=box.PROCESSED)]
		posted = D(status=reception.POSTED)
		pending = D(status=reception.PENDING_CLASSIFICATION)
		with patch.object(box, "_lines", return_value=processed), patch.object(
			box, "_box_units", return_value=[posted, pending]
		), patch.object(reception, "process_scan") as process:
			self.assertEqual(box.finish_box("BOX-2026-00001"), box.FINALIZED_WITH_EXCEPTIONS)
			process.assert_not_called()
		values = self.db.set_value.call_args.args[2]
		self.assertEqual((values["processed_lines"], values["exception_lines"]), (2, 1))
		self.db.get_value = MagicMock(return_value=box.FINALIZED_WITH_EXCEPTIONS)
		with patch.object(box, "_box_units", return_value=[posted, posted]), patch.object(
			reception, "process_scan"
		) as process:
			box.refresh_finished_box("BOX-2026-00001")
			process.assert_not_called()
		self.assertEqual(self.db.set_value.call_args.args[2]["status"], box.FINALIZED)


class TestRecovery(BoxCase):
	def test_scheduler_resumes_an_interrupted_job(self):
		"""§23.8 #3: no FINALIZING forever; only boxes without recent progress are touched."""
		stale = D(name="BOX-A", job_heartbeat=NOW - timedelta(minutes=30))
		done = D(name="BOX-B", job_heartbeat=None)
		fresh = D(name="BOX-C", job_heartbeat=NOW - timedelta(minutes=1))
		self.frappe.get_all = MagicMock(return_value=[stale, done, fresh])
		lines = {"BOX-A": [line()], "BOX-B": [line(status=box.PROCESSED)], "BOX-C": [line()]}
		with patch.object(box, "_lines", side_effect=lambda name, fields=None: lines[name]), patch.object(
			box, "enqueue_close"
		) as enqueue, patch.object(box, "finish_box") as finish:
			box.tick_from_scheduler()
		enqueue.assert_called_once_with("BOX-A")
		finish.assert_called_once_with("BOX-B")

	def test_retry_resets_only_technical_errors(self):
		self.as_role("ComercialFRA")
		self.db.get_value = MagicMock(return_value=box.FINALIZING)
		self.frappe.get_all = MagicMock(return_value=["L3"])
		with patch.object(box, "box_detail", lambda name: name):
			box.retry_box("BOX-2026-00001")
		self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"], {"box": "BOX-2026-00001", "status": box.ERROR})
		self.db.set_value.assert_called_once_with(box.LINE, "L3", "attempts", 0, update_modified=False)
		self.frappe.enqueue.assert_called_once()
		self.db.get_value = MagicMock(return_value=box.FINALIZED_WITH_EXCEPTIONS)
		with self.assertRaises(_Throw):
			box.retry_box("BOX-2026-00001")


class TestHistoryAndShopper(BoxCase):
	def test_draft_box_can_be_loaded_after_reconnect(self):
		"""§23.6 #3: a DRAFT box and its lines are read back from server persistence."""
		saved_lines = [line(), line(name="L2", status=box.DISCARDED, discarded_by="r1@fragallardo.com", discarded_on=NOW)]
		self.db.get_value = MagicMock(return_value=head())
		self.frappe.get_all = MagicMock(
			side_effect=lambda doctype, **kwargs: saved_lines if doctype == box.LINE else []
		)
		result = box.get_box("BOX-2026-00001")
		self.assertEqual(result["status"], box.DRAFT)
		self.assertEqual([row["status"] for row in result["lines"]], [box.ACTIVE, box.DISCARDED])
		self.assertEqual(result["lines"][1]["discarded_by"], "r1@fragallardo.com")
		self.db.set_value.assert_not_called()

	def test_history_by_reader(self):
		calls = []

		def get_all(doctype, **kwargs):
			calls.append((doctype, kwargs))
			if doctype == box.LINE:
				return ["BOX-1"]
			if kwargs.get("or_filters"):
				return ["BOX-2"]
			return [D(name="BOX-1")]

		self.frappe.get_all = get_all
		box.list_boxes(view="history", user="r2@fragallardo.com")
		self.assertEqual(calls[0][1]["filters"], {"scanned_by": "r2@fragallardo.com"})
		self.assertEqual(set(calls[-1][1]["filters"]["name"][1]), {"BOX-1", "BOX-2"})

	def test_search_reconstructs_box_from_barcode_item_encargo_order_or_customer(self):
		"""§23.6 #10: BOX history is discoverable through lines and received-unit links."""
		def get_all(doctype, **kwargs):
			if doctype == box.BOX:
				return ["BOX-BY-NAME"]
			if doctype == box.LINE:
				return ["BOX-BY-BARCODE"]
			return ["BOX-BY-UNIT"]

		self.frappe.get_all = MagicMock(side_effect=get_all)
		self.assertEqual(
			box._boxes_matching("needle"),
			{"BOX-BY-NAME", "BOX-BY-BARCODE", "BOX-BY-UNIT"},
		)
		unit_call = self.frappe.get_all.call_args_list[2]
		self.assertEqual(set(unit_call.kwargs["or_filters"]), {"encargo", "sales_order", "item", "customer"})
		self.assertEqual(unit_call.kwargs["filters"], {"box": ("is", "set")})

	def test_closing_box_code_is_exact(self):
		self.frappe.get_all = MagicMock(side_effect=[["BOX-1"], ["ABC"]])
		self.assertFalse(box.closing_box_has_code({"abc"}))
		self.frappe.get_all = MagicMock(side_effect=[["BOX-1"], ["abc"]])
		self.assertTrue(box.closing_box_has_code({"abc", None}))
		self.frappe.get_all = MagicMock(return_value=[])
		self.assertFalse(box.closing_box_has_code({"abc"}))
		self.assertFalse(box.closing_box_has_code({None, ""}))


if __name__ == "__main__":
	unittest.main()
