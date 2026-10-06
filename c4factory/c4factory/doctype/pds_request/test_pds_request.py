import unittest
from unittest.mock import Mock, patch

import frappe

from c4factory.api.pds_request import make_pds_request
from c4factory.c4factory.doctype.pds_request.pds_request import (
	PDSRequest,
	PDS_ITEM_SPCS_FIELDS,
	create_part_list_for_item,
	get_item_part_lists,
)


class TestPDSRequest(unittest.TestCase):
	def test_mapping_keeps_order_specs_and_excludes_rows_with_part_lists(self):
		source = Mock(name="SO-TEST", customer="Customer")
		source.name = "SO-TEST"
		source.items = [
			frappe._dict(idx=2, item_code="B", description="Second", qty=3),
			frappe._dict(idx=1, item_code="A", description="First", qty=2,
				custom_location_code="Floor", additional_notes="Notes"),
			frappe._dict(idx=3, item_code="C", part_list="C-01"),
			frappe._dict(idx=4, item_code="D", custom_part_list="D-01"),
		]
		target = Mock()
		with patch("frappe.get_doc", return_value=source), patch("frappe.new_doc", return_value=target), patch(
			"frappe.db.get_value", return_value=frappe._dict(item_name="Item", image="/files/image.jpg")
		):
			self.assertIs(make_pds_request("SO-TEST"), target)
		source.check_permission.assert_called_once_with("read")
		target.check_permission.assert_called_once_with("create")
		first = target.append.call_args_list[0].args[1]
		self.assertEqual(first["item"], "A")
		self.assertEqual(first["qty"], 2)
		self.assertFalse(first.get("part_list"))
		self.assertEqual([call.args[1]["item"] for call in target.append.call_args_list], ["A", "B"])
		self.assertEqual(first["location_code"], "Floor")
		self.assertEqual(first["additional_notes"], "Notes")

	def test_validation_accepts_draft_and_submitted_matching_part_lists(self):
		request = {"items": [frappe._dict(idx=1, item="A", part_list="A-01")]}
		for status in (0, 1):
			with patch("frappe.db.get_value", return_value=frappe._dict(product="A", disable=0, docstatus=status)):
				PDSRequest.validate(request)

	def test_validation_rejects_wrong_product_disabled_and_cancelled(self):
		request = {"items": [frappe._dict(idx=1, item="A", part_list="A-01")]}
		for mismatch in ({"product": "B"}, {"disable": 1}, {"docstatus": 2}):
			values = frappe._dict(product="A", disable=0, docstatus=0)
			values.update(mismatch)
			with patch("frappe.db.get_value", return_value=values):
				with self.assertRaises(frappe.ValidationError):
					PDSRequest.validate(request)

	def test_creation_copies_saved_values_and_persists_row_link(self):
		row = frappe._dict(name="ROW-A", item="A", description="Request description", image="/files/a.jpg",
			wood="Wood A", metal="Metal A")
		for field in PDS_ITEM_SPCS_FIELDS:
			row[field] = f"Saved {field}"
		request = Mock(docstatus=0)
		request.get.return_value = [row]
		part_list = Mock()
		part_list.name = "A-01"
		item = frappe._dict(item_name="Product A", image="/files/item.jpg", custom_width=100)
		with patch("frappe.get_doc", side_effect=[request, part_list]) as get_doc, patch(
			"frappe.get_cached_doc", return_value=item
		), patch("frappe.db.set_value") as set_value:
			self.assertEqual(create_part_list_for_item("A", pds_request="REQ", pds_request_item="ROW-A"), "A-01")
		values = get_doc.call_args_list[1].args[0]
		self.assertEqual(values["product"], "A")
		self.assertEqual(values["width"], 100)
		self.assertEqual(values["wood_color"], row.wood)
		for field in PDS_ITEM_SPCS_FIELDS:
			self.assertEqual(values[field], row[field])
		self.assertEqual(values["description"], "Request description")
		request.check_permission.assert_called_once_with("write")
		part_list.insert.assert_called_once_with(ignore_permissions=False)
		set_value.assert_called_once_with("PDS Request Item", "ROW-A", "part_list", "A-01", update_modified=False)

	def test_creation_rejects_invalid_context_before_inserting(self):
		for status, rows, selected in (
			(1, [], "ROW-A"),
			(0, [], "ROW-A"),
			(0, [frappe._dict(name="ROW-A", item="B")], "ROW-A"),
		):
			request = Mock(docstatus=status)
			request.get.return_value = rows
			with patch("frappe.get_doc", return_value=request), patch("frappe.get_cached_doc") as get_item:
				with self.assertRaises(frappe.ValidationError):
					create_part_list_for_item("A", pds_request="REQ", pds_request_item=selected)
				get_item.assert_not_called()

	def test_link_search_is_scoped_to_product_and_uses_permission_aware_list(self):
		with patch("frappe.get_list", return_value=[]) as get_list:
			get_item_part_lists("Part List", "A", "name", 0, 20, {"item": "A"})
		filters = get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["product"], "A")
		self.assertEqual(filters["disable"], 0)
		self.assertEqual(filters["docstatus"], ["<", 2])
