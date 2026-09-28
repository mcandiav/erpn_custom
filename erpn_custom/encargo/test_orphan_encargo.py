import sys
import unittest
from unittest.mock import MagicMock, patch

# Host unittest without Frappe installed; the stub must not leak into other test modules.
_stub = MagicMock()
with patch.dict(sys.modules, {"frappe": sys.modules.get("frappe") or _stub, "frappe.utils": sys.modules.get("frappe.utils") or _stub.utils}):
	from erpn_custom.encargo import sales_order_encargo


class _Row(dict):
	def get(self, key, default=None):
		return super().get(key, default)

	def __getattr__(self, key):
		return self.get(key)


class _SO:
	def __init__(self, items, docstatus=0, new=False):
		self.name = "OV-2026-00002"
		self.items = items
		self.docstatus = docstatus
		self._new = new

	def is_new(self):
		return self._new


def _drafts():
	return [
		_Row(name="ENC-2026-00007", sales_order_item="row-tote"),
		_Row(name="ENC-2026-00008", sales_order_item="row-known"),
	]


class TestOrphanDraftEncargos(unittest.TestCase):
	def _fake(self):
		fake = MagicMock()
		fake.get_all.return_value = _drafts()
		fake._ = lambda text: text
		return fake

	def _run(self, func, doc):
		fake = self._fake()
		with patch.object(sales_order_encargo, "frappe", fake), patch.object(sales_order_encargo, "_", lambda t: t):
			func(doc)
		return fake

	def _cancelled(self, fake):
		return [c.args[0 + 1] for c in fake.db.set_value.call_args_list if c.args[2:] == ("status", "Cancelled")]

	def test_removed_line_cancels_its_encargo(self):
		doc = _SO([_Row(name="row-known", custom_encargo="ENC-2026-00008"), _Row(name="row-stock")])
		fake = self._run(sales_order_encargo.cancel_orphan_draft_encargos, doc)
		self.assertEqual(self._cancelled(fake), ["ENC-2026-00007"])
		fake.msgprint.assert_called_once()

	def test_line_present_by_link_or_row_is_kept(self):
		doc = _SO([_Row(name="row-other", custom_encargo="ENC-2026-00007"), _Row(name="row-known")])
		fake = self._run(sales_order_encargo.cancel_orphan_draft_encargos, doc)
		self.assertEqual(self._cancelled(fake), [])

	def test_new_or_submitted_order_is_ignored(self):
		for doc in (_SO([], new=True), _SO([], docstatus=1)):
			fake = self._run(sales_order_encargo.cancel_orphan_draft_encargos, doc)
			self.assertFalse(fake.get_all.called)

	def test_submit_opens_only_encargos_with_line(self):
		doc = _SO([_Row(name="row-known", custom_encargo="ENC-2026-00008")], docstatus=1)
		fake = self._run(sales_order_encargo.activate_draft_encargos, doc)
		opened = [c.args[1] for c in fake.db.set_value.call_args_list]
		self.assertEqual(opened, ["ENC-2026-00008"])


if __name__ == "__main__":
	unittest.main()
