"""Item conversion validation checks runnable without a Frappe bench."""

import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from test_part_list_save import load_module


class Item(dict):
	def __getattr__(self, key):
		return self[key]


class TestItemUOM(unittest.TestCase):
	def setUp(self):
		frappe = ModuleType("frappe")
		frappe._ = lambda text: text
		def throw(message):
			raise ValueError(message)
		frappe.throw = throw
		with patch.dict(sys.modules, {"frappe": frappe}):
			self.api = load_module("c4factory/api/item_uom.py", "item_uom_test")

	def item(self, factor=300):
		return Item(stock_uom="Piece", purchase_uom="Kilogram", sales_uom=None, uoms=[
			SimpleNamespace(idx=1, uom="Piece", conversion_factor=1),
			SimpleNamespace(idx=2, uom="Kilogram", conversion_factor=factor),
		])

	def test_shared_uom_retains_different_item_factors(self):
		items = [self.item(300), self.item(200)]
		for item in items:
			self.api.validate_item_uoms(item)
		self.assertEqual([item.uoms[1].conversion_factor for item in items], [300, 200])

	def test_invalid_factors_are_rejected(self):
		for factor in (None, 0, -1, "invalid", float("nan"), float("inf")):
			with self.subTest(factor=factor), self.assertRaisesRegex(ValueError, "positive"):
				self.api.validate_item_uoms(self.item(factor))

	def test_fractional_factor_is_allowed(self):
		self.api.validate_item_uoms(self.item(0.5))

	def test_default_factor_must_be_one(self):
		item = self.item()
		item.uoms[0].conversion_factor = 2
		with self.assertRaisesRegex(ValueError, "must be 1"):
			self.api.validate_item_uoms(item)

	def test_duplicate_and_empty_units_are_rejected(self):
		for uom, message in (("Piece", "already listed"), (None, "Select a UOM")):
			item = self.item()
			item.uoms[1].uom = uom
			with self.assertRaisesRegex(ValueError, message):
				self.api.validate_item_uoms(item)

	def test_purchase_and_sales_uoms_require_item_conversion(self):
		for field in ("purchase_uom", "sales_uom"):
			item = self.item()
			item[field] = "Box"
			with self.assertRaisesRegex(ValueError, "Add UOM Box"):
				self.api.validate_item_uoms(item)

	def test_default_transaction_uom_needs_no_additional_row(self):
		self.api.validate_item_uoms(Item(stock_uom="Piece", purchase_uom="Piece", sales_uom="Piece", uoms=[]))


if __name__ == "__main__":
	unittest.main()
