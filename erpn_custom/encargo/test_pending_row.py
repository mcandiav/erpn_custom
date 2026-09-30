import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = sys.modules.get("frappe") or MagicMock()
_stubs = {
	"frappe": _frappe,
	"frappe.utils": sys.modules.get("frappe.utils") or MagicMock(),
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
	def test_reuses_technical_line_without_encargo(self):
		real = _Row(item_code="ITEM-A", custom_encargo=None)
		pending = _Row(item_code=ENCARGO_PENDIENTE_ITEM, custom_encargo=None)
		found = _unlinked_pending_row(_SO([real, pending]))
		self.assertIs(found, pending)

	def test_appends_when_technical_line_already_has_encargo(self):
		linked = _Row(item_code=ENCARGO_PENDIENTE_ITEM, custom_encargo="ENC-1")
		self.assertIsNone(_unlinked_pending_row(_SO([linked])))
