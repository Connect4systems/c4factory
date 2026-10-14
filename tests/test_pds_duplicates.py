"""Duplicate request checks without a local Frappe bench."""

import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module


class Doc(dict):
	@property
	def items(self):
		return self.get("items", [])

	def __getattr__(self, key):
		return self.get(key)

	def __setattr__(self, key, value):
		self[key] = value

	def append(self, field, values):
		self.setdefault(field, []).append(Doc(values))


class TestPDSDuplicates(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe._ = lambda message: message
		self.frappe.whitelist = lambda: lambda fn: fn
		self.frappe.throw = Mock(side_effect=ValueError)
		self.frappe.db = Mock()
		self.frappe.db.sql.return_value = []
		self.frappe.get_all = Mock(return_value=[])
		utils = ModuleType("frappe.utils")
		utils.today = lambda: "2026-10-14"
		utils.now_datetime = lambda: "NOW"
		with patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": utils}):
			self.api = load_module("c4factory/api/pds_request.py", "pds_duplicates_test")

	def request(self, items, previous=None):
		return Doc(name="NEW", items=items, get_doc_before_save=lambda: previous)

	def test_blockers_include_part_lists_and_previous_requests(self):
		self.frappe.get_all.return_value = [Doc(product="A", name="PL-A")]
		self.frappe.db.sql.return_value = [Doc(item="B", name="PDS-B")]
		blocked = self.api.get_pds_item_blockers(["A", "B", "C"], "CURRENT")
		self.assertEqual(set(blocked), {"A", "B"})
		self.assertIn("PL-A", blocked["A"])
		self.assertIn("PDS-B", blocked["B"])
		self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"]["docstatus"], ["<", 2])
		self.assertIn("r.docstatus < 2", self.frappe.db.sql.call_args.args[0])
		self.assertEqual(self.frappe.db.sql.call_args.args[1]["exclude"], "CURRENT")

	def test_new_and_changed_rows_are_checked_under_item_lock(self):
		for previous in (None, Doc(items=[Doc(name="ROW", item="OLD")])):
			with self.subTest(previous=previous):
				self.frappe.db.sql.reset_mock()
				with patch.object(self.api, "get_pds_item_blockers", return_value={"A": "an existing Part List"}):
					with self.assertRaises(ValueError):
						self.api.validate_new_pds_items(self.request([Doc(name="ROW", item="A", idx=1)], previous))
				self.assertIn("for update", self.frappe.db.sql.call_args.args[0])

	def test_existing_row_can_be_edited_after_part_list_created(self):
		previous = Doc(items=[Doc(name="ROW", item="A")])
		self.api.validate_new_pds_items(self.request([Doc(name="ROW", item="A", part_list="PL", idx=1)], previous))
		self.frappe.get_all.assert_not_called()
		self.frappe.db.sql.assert_not_called()

	def test_duplicate_item_in_same_request_rejected(self):
		with self.assertRaises(ValueError):
			self.api.validate_new_pds_items(self.request([
				Doc(name="1", item="A", idx=1), Doc(name="2", item="A", idx=2),
			]))

	def test_mapping_skips_existing_and_repeated_items(self):
		rows = [Doc(name=str(i), idx=i, item_code=item, description="Spec", qty=1)
			for i, item in enumerate(("A", "B", "C", "C", "D"), 1)]
		rows[-1].custom_part_list = "PL-D"
		self.frappe.get_doc = Mock(return_value=Doc(name="SO", customer="Customer", items=rows, check_permission=Mock()))
		self.frappe.new_doc = Mock(return_value=Doc(check_permission=Mock()))
		self.frappe.db.get_value.return_value = {"item_name": "Product", "image": "image.png"}
		with patch.object(self.api, "get_pds_item_blockers", return_value={"A": "Part List", "B": "Request"}):
			result = self.api.make_pds_request("SO")
		self.assertEqual([row.item for row in result.items], ["C"])
		self.assertEqual(result.items[0].sales_order_item, "3")

	def test_mapping_all_blocked_shows_message(self):
		self.frappe.get_doc = Mock(return_value=Doc(name="SO", customer="Customer", items=[
			Doc(idx=1, item_code="A")], check_permission=Mock()))
		self.frappe.new_doc = Mock(return_value=Doc(check_permission=Mock()))
		with patch.object(self.api, "get_pds_item_blockers", return_value={"A": "Request"}):
			with self.assertRaises(ValueError):
				self.api.make_pds_request("SO")


if __name__ == "__main__":
	unittest.main()
