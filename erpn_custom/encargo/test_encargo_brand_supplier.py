import sys
import unittest
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
_frappe._ = lambda msg: msg
_frappe.whitelist = lambda *a, **k: (lambda f: f)
_frappe.validate_and_sanitize_search_inputs = lambda f: f
_frappe.utils = MagicMock()
_frappe.utils.flt = lambda v, *a, **k: float(v or 0)
_frappe.utils.cint = lambda v: 1 if int(v or 0) else 0


class _Throw(Exception):
	pass


def _throw(msg, *a, **k):
	raise _Throw(msg)


_frappe.throw = _throw
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)
sys.modules.setdefault("frappe.utils.file_manager", MagicMock())


class Document:
	def __init__(self, *a, **k):
		pass

	def is_new(self):
		return getattr(self, "_is_new", True)


_doc_mod = MagicMock()
_doc_mod.Document = Document
sys.modules.setdefault("frappe.model.document", _doc_mod)

from erpn_custom.encargo.doctype.encargo.encargo import Encargo  # noqa: E402


class TestEncargoBrandSupplier(unittest.TestCase):
	def test_unknown_insert_requires_brand(self):
		doc = Encargo()
		doc._is_new = True
		doc.source_type = "UNKNOWN_ITEM"
		doc.brand = None
		doc.supplier = None
		doc.purchase_status = "PENDING"
		doc.reception_status = "PENDING"
		doc.status = "Draft"
		with self.assertRaises(Exception):
			doc.before_insert()

	@patch("erpn_custom.encargo.doctype.encargo.encargo.require_brand", return_value="Michael Kors")
	def test_unknown_insert_ok_brand_only(self, _req):
		doc = Encargo()
		doc._is_new = True
		doc.source_type = "UNKNOWN_ITEM"
		doc.brand = "Michael Kors"
		doc.supplier = None
		doc.purchase_status = "PENDING"
		doc.reception_status = "PENDING"
		doc.status = "Draft"
		doc.before_insert()
		self.assertEqual(doc.brand, "Michael Kors")


if __name__ == "__main__":
	unittest.main()
