import unittest

from erpn_custom.encargo.stock_split import (
	allocate_available_across_rows,
	available_to_sell,
	split_qty,
)


class TestStockSplit(unittest.TestCase):
	def test_full_stock_no_encargo(self):
		stock, enc = split_qty(2, 5)
		self.assertEqual(stock, 2)
		self.assertEqual(enc, 0)

	def test_partial_stock(self):
		stock, enc = split_qty(3, 1)
		self.assertEqual(stock, 1)
		self.assertEqual(enc, 2)

	def test_zero_stock(self):
		stock, enc = split_qty(1, 0)
		self.assertEqual(stock, 0)
		self.assertEqual(enc, 1)

	def test_available_to_sell(self):
		self.assertEqual(available_to_sell(18, 2), 16)
		self.assertEqual(available_to_sell(1, 5), 0)

	def test_allocate_across_duplicate_rows(self):
		rows = [{"qty": 2}, {"qty": 2}]
		alloc = allocate_available_across_rows(rows, 3)
		self.assertEqual(alloc, [(2, 0), (1, 1)])
