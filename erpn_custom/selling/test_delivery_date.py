import sys
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

_frappe = MagicMock()
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

from erpn_custom.selling.delivery_date import default_delivery_date  # noqa: E402

_MOD = "erpn_custom.selling.delivery_date"


class _SO(dict):
	doctype = "Sales Order"

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.__dict__ = self
		self.setdefault("docstatus", 0)


def _add_days(value, days):
	return date.fromisoformat(str(value)) + timedelta(days=days)


@patch(f"{_MOD}.nowdate", return_value="2026-09-30")
@patch(f"{_MOD}.add_days", side_effect=_add_days)
class TestDefaultDeliveryDate(unittest.TestCase):
	def test_empty_date_is_order_date_plus_seven(self, _add, _now):
		doc = _SO(transaction_date="2026-10-01", delivery_date=None)
		default_delivery_date(doc)
		self.assertEqual(doc.delivery_date, date(2026, 10, 8))

	def test_without_order_date_uses_today(self, _add, _now):
		doc = _SO(transaction_date=None, delivery_date=None)
		default_delivery_date(doc)
		self.assertEqual(doc.delivery_date, date(2026, 10, 7))

	def test_seller_date_is_kept(self, _add, _now):
		doc = _SO(transaction_date="2026-10-01", delivery_date="2026-10-03")
		default_delivery_date(doc)
		self.assertEqual(doc.delivery_date, "2026-10-03")

	def test_submitted_order_untouched(self, _add, _now):
		doc = _SO(transaction_date="2026-10-01", delivery_date=None, docstatus=1)
		default_delivery_date(doc)
		self.assertIsNone(doc.delivery_date)


if __name__ == "__main__":
	unittest.main()
