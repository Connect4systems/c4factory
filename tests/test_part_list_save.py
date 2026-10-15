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
		document.Document = type("Document", (), {"get": lambda self, key: getattr(self, key, None), "get_doc_before_save": lambda self: None})
		self.modules = patch.dict(sys.modules, {
			"frappe": self.frappe,
			"frappe.model": ModuleType("frappe.model"),
			"frappe.model.document": document,
		})
		self.modules.start()
		self.addCleanup(self.modules.stop)
		self.controller = load_module("c4factory/c4factory/doctype/part_list/part_list.py", "part_list_test")

	def test_save_and_submit_fetch_material_line_without_removed_headers(self):
		self.frappe.db.get_value.return_value = "LINE-1"
		for status in (0, 1):
			part = self.controller.PartList()
			part.product = "CUBE"
			part.docstatus = status
			part.before_validate()
			self.assertEqual(part.material_line, "LINE-1")
			self.assertEqual(part.metal_material_line, "LINE-1")
			self.assertFalse(hasattr(part, "wood_type"))
			self.assertFalse(hasattr(part, "wood_color_doctype"))

	def test_empty_product_clears_both_material_lines(self):
		part = self.controller.PartList()
		part.product = None
		part.before_validate()
		self.assertIsNone(part.material_line)
		self.assertIsNone(part.metal_material_line)
		self.frappe.db.get_value.assert_not_called()

	def test_manual_material_line_and_copied_image_survive_save(self):
		part = self.controller.PartList()
		part.material_line = "User Selection"
		part.metal_material_line = "User Selection"
		part.product_image = "copied.png"
		part.before_validate()
		self.assertEqual(part.material_line, "User Selection")
		self.assertEqual(part.product_image, "copied.png")
		self.frappe.db.get_value.assert_not_called()

	def test_editing_metal_material_line_updates_shared_value(self):
		part = self.controller.PartList()
		part.material_line = "Original"
		part.metal_material_line = "Metal Tab Selection"
		part.get_doc_before_save = lambda: {"material_line": "Original", "metal_material_line": "Original"}
		part.before_validate()
		self.assertEqual(part.material_line, "Metal Tab Selection")

	def test_version_becomes_default_only_on_submission(self):
		part = self.controller.PartList()
		part.version_of = "CUBE-01"
		part.is_default = 0
		part.before_submit()
		self.assertEqual(part.is_default, 1)

	def test_all_tables_use_part_material_color_configuration(self):
		api = load_module("c4factory/api/part_list_material_colors.py", "material_colors_test")
		self.frappe.db.get_value.return_value = "Wood"
		for table in ("panel_materials", "metal_material", "other_material"):
			self.assertEqual(api.material_color_target(
				SimpleNamespace(doctype="Part List"), table, SimpleNamespace(material="Natural Wood", get=lambda key: None)
			), "Material Color")

	def test_submit_still_updates_originating_sales_order(self):
		api = ModuleType("c4factory.api.pds_request")
		api.update_sales_order_part_list = Mock()
		part = self.controller.PartList()
		part.is_default = 0
		versions = ModuleType("c4factory.api.part_list_versions")
		versions.activate_for_product = Mock()
		with patch.dict(sys.modules, {"c4factory.api.pds_request": api, "c4factory.api.part_list_versions": versions}):
			part.on_submit()
		api.update_sales_order_part_list.assert_called_once_with(part)


if __name__ == "__main__":
	unittest.main()
