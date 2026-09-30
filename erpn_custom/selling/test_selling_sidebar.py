import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.modules.setdefault("frappe", MagicMock())

from erpn_custom.selling.selling_sidebar import insert_encargo_link  # noqa: E402


def _row(link_to, child=0, link_type="DocType"):
	return SimpleNamespace(link_type=link_type, link_to=link_to, child=child, idx=0)


class _Sidebar:
	def __init__(self, rows):
		self.items = rows

	def append(self, _field, values):
		row = SimpleNamespace(idx=0, **values)
		self.items.append(row)
		return row


def _links(doc):
	return [row.link_to for row in doc.items]


class TestInsertEncargoLink(unittest.TestCase):
	def _standard(self):
		return _Sidebar(
			[
				_row("Selling", link_type="Workspace"),
				_row("Quotation"),
				_row("Sales Order"),
				_row("Sales Invoice"),
				_row("Customer", child=1),
			]
		)

	def test_inserted_right_after_sales_order(self):
		doc = self._standard()
		self.assertTrue(insert_encargo_link(doc))
		self.assertEqual(_links(doc), ["Selling", "Quotation", "Sales Order", "Encargo", "Sales Invoice", "Customer"])
		self.assertEqual([row.idx for row in doc.items], [1, 2, 3, 4, 5, 6])
		self.assertEqual(doc.items[3].label, "Encargos (ENC)")

	def test_idempotent(self):
		doc = self._standard()
		insert_encargo_link(doc)
		self.assertFalse(insert_encargo_link(doc))
		self.assertEqual(_links(doc).count("Encargo"), 1)

	def test_without_sales_order_leaves_sidebar_untouched(self):
		doc = _Sidebar([_row("Selling", link_type="Workspace"), _row("Quotation")])
		self.assertFalse(insert_encargo_link(doc))
		self.assertEqual(_links(doc), ["Selling", "Quotation"])


if __name__ == "__main__":
	unittest.main()
