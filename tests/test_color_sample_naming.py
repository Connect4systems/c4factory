import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module


class Doc(dict):
	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__


class TestColorSampleNaming(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe._ = lambda message: message
		self.frappe.throw = Mock(side_effect=ValueError)
		self.frappe.db = Mock()
		self.frappe.db.get_value.return_value = "Office Desk"
		self.source = Doc(name="ROW", item_name="Office Desk", item_code="DESK")
		self.order = Doc(custom_project_no=" P-123 ", items=[self.source], check_permission=Mock())
		self.frappe.get_doc = Mock(return_value=self.order)
		naming = ModuleType("frappe.model.naming")
		naming.getseries = Mock(return_value="01")
		with patch.dict(sys.modules, {"frappe": self.frappe, "frappe.model.naming": naming}):
			self.api = load_module("c4factory/api/color_sample_naming.py", "sample_naming_test")
		self.doc = Doc(sales_order="SO", items=[Doc(sales_order_item="ROW")])

	def test_project_number_and_item_name_with_two_digit_sequence(self):
		self.api.set_sample_name(self.doc)
		self.assertEqual(self.doc.name, "P-123-Office Desk-01")
		self.api.getseries.assert_called_once_with("P-123-Office Desk-", 2)
		self.order.check_permission.assert_called_once_with("read")
		self.frappe.db.get_value.assert_called_once_with("Item", "DESK", "item_name")

	def test_name_uses_product_item_master_instead_of_order_row_name(self):
		self.source.item_name = "Sales Order Description"
		self.frappe.db.get_value.return_value = "Product Desk"
		self.api.set_sample_name(self.doc)
		self.assertEqual(self.doc.name, "P-123-Product Desk-01")

	def test_first_item_determines_name_for_multiple_item_sample(self):
		self.doc["items"].append(Doc(sales_order_item="SECOND"))
		self.api.set_sample_name(self.doc)
		self.assertEqual(self.doc.name, "P-123-Office Desk-01")

	def test_sequence_is_scoped_to_project_and_item(self):
		self.api.getseries.side_effect = ["01", "02"]
		self.api.set_sample_name(self.doc)
		self.assertEqual(self.doc.name, "P-123-Office Desk-01")
		self.api.set_sample_name(self.doc)
		self.assertEqual(self.doc.name, "P-123-Office Desk-02")

	def test_project_number_fallback(self):
		self.order.custom_project_no = ""
		self.order.project = "PROJ"
		self.frappe.get_doc.side_effect = [self.order, Doc(project_no="P-456")]
		self.api.set_sample_name(self.doc)
		self.assertEqual(self.doc.name, "P-456-Office Desk-01")

	def test_missing_project_or_invalid_row_rejected(self):
		self.order.custom_project_no = ""
		with self.assertRaises(ValueError):
			self.api.set_sample_name(self.doc)
		self.order.custom_project_no = "P-123"
		self.doc["items"][0].sales_order_item = "OTHER"
		with self.assertRaises(ValueError):
			self.api.set_sample_name(self.doc)


if __name__ == "__main__":
	unittest.main()
