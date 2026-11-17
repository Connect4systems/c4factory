"""Unlinking preserves documents and checks permissions before writes."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_part_list_save import TestPartListSave, load_module


class TestPartListLinks(TestPartListSave):
	def setUp(self):
		super().setUp()
		self.api = load_module("c4factory/api/part_list_links.py", "part_list_links_test")
		self.meta = Mock(fields=[SimpleNamespace(fieldname="part_list", fieldtype="Link", options="Part List")])
		self.meta.has_field.return_value = False
		self.frappe.get_meta = Mock(return_value=self.meta)
		self.frappe.get_all = Mock(return_value=[])
		self.frappe.get_doc = Mock()
		self.frappe.utils = Mock()

	def test_unlink_only_matching_reference(self):
		row = SimpleNamespace(parent="PDS-1", get=Mock())
		row.name = "ROW-1"
		row.get.return_value = "PART-1"
		self.frappe.get_all.side_effect = [[], [row]]
		self.assertEqual(self.api.unlink_references(SimpleNamespace(name="PART-1")), 1)
		self.frappe.db.set_value.assert_any_call(
			"PDS Request Item", "ROW-1", {"part_list": None}, update_modified=False)
		self.frappe.get_doc.return_value.check_permission.assert_called_with("write")

	def test_parent_permission_failure_does_not_write(self):
		row = SimpleNamespace(parent="PDS-1", get=Mock())
		row.name = "ROW-1"
		self.frappe.get_all.side_effect = [[], [row]]
		self.frappe.get_doc.return_value.check_permission.side_effect = PermissionError
		with self.assertRaises(PermissionError):
			self.api.unlink_references(SimpleNamespace(name="PART-1"))
		self.frappe.db.set_value.assert_not_called()

	def test_endpoint_checks_cancel_permission_before_unlink(self):
		part = self.frappe.get_doc.return_value
		part.docstatus = 1
		with patch.object(self.api, "unlink_references", return_value=2) as unlink:
			self.assertEqual(self.api.unlink_part_list("PART-1"), 2)
		part.check_permission.assert_any_call("write")
		part.check_permission.assert_any_call("cancel")
		unlink.assert_called_once_with(part)


if __name__ == "__main__":
	unittest.main()

