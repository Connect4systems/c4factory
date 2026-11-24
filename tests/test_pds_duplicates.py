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
		self.frappe.validate_and_sanitize_search_inputs = lambda fn: fn
		self.frappe.throw = Mock(side_effect=ValueError)
		self.frappe.db = Mock()
		self.frappe.db.sql.return_value = []
		self.frappe.get_all = Mock(return_value=[])
		utils = ModuleType("frappe.utils")
		utils.today = lambda: "2026-10-14"
		utils.now_datetime = lambda: "NOW"
		with patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": utils}):
			self.api = load_module("c4factory/api/pds_request.py", "pds_duplicates_test")
			self.boq_api = load_module("c4factory/api/boq_items.py", "boq_items_test")
		self.frappe.get_meta = Mock(return_value=Doc(fields=[
			Doc(fieldname="custom_item_type", fieldtype="Link", options="Item Type")]))
		modules = patch.dict(sys.modules, {"c4factory.api.boq_items": self.boq_api})
		modules.start()
		self.addCleanup(modules.stop)

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
		self.frappe.get_all.side_effect = [["BOQ"], ["A", "B", "C", "D"]]
		with patch.object(self.api, "get_pds_item_blockers", return_value={"A": "Part List", "B": "Request"}):
			result = self.api.make_pds_request("SO")
		self.assertEqual([row.item for row in result.items], ["C"])
		self.assertEqual(result.items[0].sales_order_item, "3")

	def test_mapping_excludes_items_without_boq_required_type(self):
		self.frappe.get_doc = Mock(return_value=Doc(name="SO", customer="Customer", items=[
			Doc(name=item, idx=i, item_code=item, qty=1)
			for i, item in enumerate(["BOQ-ITEM", "NON-BOQ", "NO-TYPE"], 1)
		], check_permission=Mock()))
		self.frappe.new_doc = Mock(return_value=Doc(check_permission=Mock()))
		self.frappe.db.get_value.return_value = {}
		self.frappe.get_all.side_effect = [["BOQ-TYPE"], ["BOQ-ITEM"]]
		with patch.object(self.api, "get_pds_item_blockers", return_value={}):
			result = self.api.make_pds_request("SO")
		self.assertEqual([row.item for row in result.items], ["BOQ-ITEM"])
		self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"]["custom_item_type"], ["in", ["BOQ-TYPE"]])

	def test_product_picker_requires_enabled_sales_and_boq_type(self):
		self.frappe.get_all.return_value = ["BOQ-TYPE"]
		self.frappe.get_list = Mock(return_value=[["A", "Product A"]])
		self.assertEqual(self.boq_api.get_part_list_products("Item", "A", "name", 20, 10), [["A", "Product A"]])
		args = self.frappe.get_list.call_args.kwargs
		self.assertEqual(args["filters"], {
			"custom_item_type": ["in", ["BOQ-TYPE"]], "disabled": 0, "is_sales_item": 1})
		self.assertEqual((args["start"], args["page_length"]), (20, 10))

	def test_automatic_request_copies_team_specs_and_first_row_quantity(self):
		source = Doc(name="SO", customer="Customer", custom_technical_team="Design", items=[
			Doc(name="FIRST", idx=1, item_code="A", qty=2, custom_location_code="Room",
				custom_sub_code="Sub", custom_panel_specs="Panel\nDetails", custom_metal_specs="Metal", custom_other_specs="Other"),
			Doc(name="SECOND", idx=2, item_code="A", qty=5),
		])
		target = Doc(check_permission=Mock())
		self.frappe.new_doc = Mock(return_value=target)
		self.frappe.get_all.side_effect = [["BOQ"], ["A"]]
		self.frappe.db.get_value.return_value = {}
		with patch.object(self.api, "get_pds_item_blockers", return_value={}):
			result = self.api.build_pds_request(source, automatic=True)
		self.assertEqual(result.technical_team, "Design")
		self.assertEqual(len(result.items), 1)
		self.assertEqual(result.items[0].qty, 2)
		self.assertEqual(result.items[0].sales_order_item, "FIRST")
		for field, value in {"location_code": "Room", "sub_code": "Sub", "panel_specs": "Panel\nDetails", "metal_specs": "Metal", "other_specs": "Other"}.items():
			self.assertEqual(result.items[0][field], value)
		self.assertNotIn("leather", result.items[0])
		self.assertNotIn("other", result.items[0])
		target.check_permission.assert_not_called()

	def test_automatic_empty_request_is_skipped(self):
		self.frappe.new_doc = Mock(return_value=Doc())
		with patch.object(self.api, "get_pds_item_blockers", return_value={}):
			self.assertIsNone(self.api.build_pds_request(Doc(name="SO", customer="C", items=[]), automatic=True))
		self.frappe.throw.assert_not_called()

	def test_submit_saves_draft_under_item_locks(self):
		source = Doc(name="SO", docstatus=1, items=[Doc(item_code="B"), Doc(item_code="A"), Doc(item_code="A")])
		self.frappe.db.exists.return_value = False
		request = Doc(insert=Mock())
		with patch.object(self.api, "build_pds_request", return_value=request) as build:
			self.api.on_sales_order_submit(source)
		build.assert_called_once_with(source, automatic=True)
		self.assertEqual(request.docstatus, 0)
		request.insert.assert_called_once_with(ignore_permissions=True)
		self.assertEqual([call.args[1] for call in self.frappe.db.sql.call_args_list], [("A",), ("B",)])

	def test_submit_skips_drafts_existing_requests_and_empty_results(self):
		with patch.object(self.api, "build_pds_request", return_value=None) as build:
			self.api.on_sales_order_submit(Doc(name="SO", docstatus=0))
			build.assert_not_called()
			self.frappe.db.exists.return_value = True
			self.api.on_sales_order_submit(Doc(name="SO", docstatus=1, items=[]))
			build.assert_not_called()
			self.frappe.db.exists.return_value = False
			self.api.on_sales_order_submit(Doc(name="SO", docstatus=1, items=[]))
			build.assert_called_once()

	def test_insert_failure_propagates_to_roll_back_submission(self):
		self.frappe.db.exists.return_value = False
		request = Doc(insert=Mock(side_effect=ValueError("Cannot save request")))
		with patch.object(self.api, "build_pds_request", return_value=request):
			with self.assertRaisesRegex(ValueError, "Cannot save request"):
				self.api.on_sales_order_submit(Doc(name="SO", docstatus=1, items=[]))

	def test_mapping_all_blocked_shows_message(self):
		self.frappe.get_doc = Mock(return_value=Doc(name="SO", customer="Customer", items=[
			Doc(idx=1, item_code="A")], check_permission=Mock()))
		self.frappe.new_doc = Mock(return_value=Doc(check_permission=Mock()))
		with patch.object(self.api, "get_pds_item_blockers", return_value={"A": "Request"}):
			with self.assertRaises(ValueError):
				self.api.make_pds_request("SO")


if __name__ == "__main__":
	unittest.main()
