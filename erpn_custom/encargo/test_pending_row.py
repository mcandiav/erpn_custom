import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = sys.modules.get("frappe") or MagicMock()
_utils = sys.modules.get("frappe.utils") or MagicMock()
_stubs = {
	"frappe": _frappe,
	"frappe.utils": _utils,
	"frappe.utils.file_manager": sys.modules.get("frappe.utils.file_manager") or MagicMock(),
	"frappe.model": sys.modules.get("frappe.model") or MagicMock(),
	"frappe.model.document": sys.modules.get("frappe.model.document") or MagicMock(),
}

with patch.dict(sys.modules, _stubs):
	from erpn_custom.encargo.api import _unlinked_pending_row

from erpn_custom.encargo import ENCARGO_PENDIENTE_ITEM


class _Row(dict):
	def get(self, key, default=None):
		return super().get(key, default)

	def __getattr__(self, key):
		return self.get(key)


class _SO:
	def __init__(self, items):
		self.items = items


class TestUnlinkedPendingRow(unittest.TestCase):
	def test_reuses_row_without_encargo(self):
		linked = _Row(item_code=ENCARGO_PENDIENTE_ITEM, custom_encargo="ENC-1")
		pending = _Row(item_code=ENCARGO_PENDIENTE_ITEM, custom_encargo=None)
		found = _unlinked_pending_row(_SO([linked, pending]))
		self.assertIs(found, pending)

	def test_ignores_linked_and_real_items(self):
		rows = [
			_Row(item_code="ITEM-A", custom_encargo=None),
			_Row(item_code=ENCARGO_PENDIENTE_ITEM, custom_encargo="ENC-1"),
		]
		self.assertIsNone(_unlinked_pending_row(_SO(rows)))
