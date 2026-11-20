"""Color Samples require submitted technical data, independently of stock linking."""

import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from test_part_list_save import load_module


class Doc(dict):
    def __getattr__(self, key):
        return self[key]


class TestColorSampleApproval(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda message: message
        self.frappe.whitelist = lambda: lambda fn: fn
        self.frappe.throw = Mock(side_effect=ValueError)
        self.frappe.get_doc = Mock()
        utils = ModuleType("frappe.utils")
        utils.flt = lambda value: float(value or 0)
        utils.today = lambda: "2026-11-21"
        colors = ModuleType("c4factory.api.sales_order_colors")
        colors.get_part_list_colors = Mock(return_value={"rows": []})
        colors.validate_colors = Mock()
        self.colors = colors
        with patch.dict(sys.modules, {
            "frappe": self.frappe, "frappe.utils": utils,
            "c4factory.api.sales_order_colors": colors,
        }):
            self.api = load_module("c4factory/api/color_sample.py", "sample_approval_test")

    def test_draft_cancelled_and_missing_part_lists_block_samples(self):
        for status in (0, 2):
            self.frappe.get_doc.return_value = SimpleNamespace(docstatus=status, check_permission=Mock())
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.api.source_colors(Doc(custom_part_list="PL", item_code="DESK"))
        self.colors.get_part_list_colors.assert_not_called()
        self.frappe.throw.assert_called_with(
            "Part List PL for item DESK must be submitted by Technical before creating a Color Sample."
        )
        with self.assertRaises(ValueError):
            self.api.source_colors(Doc(item_code="DESK"))

    def test_pending_and_partly_linked_submitted_parts_allow_samples(self):
        for status in ("Pending Linking", "Partly Linked", "Completed"):
            part = SimpleNamespace(docstatus=1, accessory_linking_status=status, check_permission=Mock())
            self.frappe.get_doc.return_value = part
            result = self.api.source_colors(Doc(custom_part_list="PL", item_code="DESK"))
            self.assertEqual(result["custom_part_list"], "PL")
            part.check_permission.assert_called_once_with("read")


if __name__ == "__main__":
    unittest.main()
