import unittest
from unittest.mock import Mock, patch

from c4factory.api import sales_order_part_list as api


class Doc(dict):
	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__


class TestSalesOrderPartList(unittest.TestCase):
	def test_submitted_sample_blocks_change(self):
		with patch.object(api.frappe.db, "sql", side_effect=[[], [("SAMPLE-1",)]]), patch.object(
			api.frappe, "throw", side_effect=ValueError
		), self.assertRaises(ValueError):
			api.check_part_list_change("SO-1", "ROW-1")

	def test_no_submitted_sample_allows_change(self):
		with patch.object(api.frappe.db, "sql", return_value=[]) as sql, patch.object(api.frappe, "throw") as throw:
			api.check_part_list_change("SO-1", "ROW-1")
		throw.assert_not_called()
		query, args = sql.call_args.args
		self.assertIn("s.docstatus = 1", query)
		self.assertIn("for update", query)
		self.assertEqual(args, ("SO-1", "ROW-1"))

	def test_update_rebuilds_colors_only_for_changed_row(self):
		old = Doc(name="ROW-1", custom_part_list="OLD")
		row = Doc(name="ROW-1", idx=1, item_code="ITEM", custom_part_list="NEW", custom_color_sample_data="old")
		doc = Mock(name="order")
		doc.name = "SO-1"
		doc.items = [row]
		doc.get_doc_before_save.return_value = Mock(items=[old])
		meta = Mock(fields=[Doc(fieldname="custom_part_list", fieldtype="Link", options="Part List")])
		with patch.object(api.frappe, "get_meta", return_value=meta), patch.object(
			api, "check_part_list_change"
		) as check, patch.object(api.frappe, "get_doc", return_value=Doc(docstatus=1, product="ITEM")), patch(
			"c4factory.api.sales_order_colors.validate_colors"
		) as validate:
			api.before_update_after_submit(doc)
		check.assert_called_once_with("SO-1", "ROW-1")
		self.assertIsNone(row.custom_color_sample_data)
		self.assertNotIn("custom_wood_color_doctype", row)
		self.assertEqual(validate.call_args.args[0].items, [row])

	def test_unchanged_part_list_does_not_check_samples(self):
		row = Doc(name="ROW-1", custom_part_list="PL")
		doc = Mock()
		doc.items = [row]
		doc.get_doc_before_save.return_value = Mock(items=[row])
		meta = Mock(fields=[Doc(fieldname="custom_part_list", fieldtype="Link", options="Part List")])
		with patch.object(api.frappe, "get_meta", return_value=meta), patch.object(api, "check_part_list_change") as check:
			api.before_update_after_submit(doc)
		check.assert_not_called()
