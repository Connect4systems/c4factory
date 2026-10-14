"""Controller checks that can run without a local Frappe bench."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
	spec = importlib.util.spec_from_file_location(name, ROOT / path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class TestPartListSave(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe.db = Mock()
		self.frappe._ = lambda value: value
		document = ModuleType("frappe.model.document")
		document.Document = type("Document", (), {})
		self.modules = patch.dict(sys.modules, {
			"frappe": self.frappe,
			"frappe.model": ModuleType("frappe.model"),
			"frappe.model.document": document,
		})
		self.modules.start()
		self.addCleanup(self.modules.stop)
		self.controller = load_module("c4factory/c4factory/doctype/part_list/part_list.py", "part_list_test")

	def test_save_and_submit_fetch_material_line_without_removed_headers(self):
		self.frappe.db.get_value.return_value = {"custom_material_line": "LINE-1", "image": "image.png"}
		for status in (0, 1):
			part = self.controller.PartList()
			part.product = "CUBE"
			part.docstatus = status
			part.before_validate()
			self.assertEqual(part.material_line, "LINE-1")
			self.assertEqual(part.metal_material_line, "LINE-1")
			self.assertEqual(part.product_image, "image.png")
			self.assertFalse(hasattr(part, "wood_type"))
			self.assertFalse(hasattr(part, "wood_color_doctype"))

	def test_empty_product_clears_both_material_lines(self):
		part = self.controller.PartList()
		part.product = None
		part.before_validate()
		self.assertIsNone(part.material_line)
		self.assertIsNone(part.metal_material_line)
		self.frappe.db.get_value.assert_not_called()

	def test_all_tables_use_part_material_color_configuration(self):
		api = load_module("c4factory/api/part_list_material_colors.py", "material_colors_test")
		self.frappe.db.get_value.return_value = "P-Natural"
		for table in ("panel_materials", "metal_material", "other_material"):
			self.assertEqual(api.material_color_target(
				SimpleNamespace(doctype="Part List"), table, SimpleNamespace(material="Natural Wood")
			), "P-Natural")

	def test_submit_still_updates_originating_sales_order(self):
		api = ModuleType("c4factory.api.pds_request")
		api.update_sales_order_part_list = Mock()
		part = self.controller.PartList()
		with patch.dict(sys.modules, {"c4factory.api.pds_request": api}):
			part.on_submit()
		api.update_sales_order_part_list.assert_called_once_with(part)


if __name__ == "__main__":
	unittest.main()
