import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_part_list_save import ROOT, TestPartListSave, load_module


class Doc(dict):
	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value


class TestSalesOrderColorCleanup(TestPartListSave):
	def load_colors(self):
		self.frappe.whitelist = lambda: lambda function: function
		materials = load_module("c4factory/api/part_list_material_colors.py", "cleanup_material_colors")
		with patch.dict(sys.modules, {"c4factory.api.part_list_material_colors": materials}):
			return load_module("c4factory/api/sales_order_colors.py", "cleanup_order_colors")

	def test_sales_order_validation_preserves_row_choices_without_headers(self):
		api = self.load_colors()
		item = Doc(doctype="Sales Order Item", idx=1, custom_part_list="PL", meta=Mock())
		item.custom_color_sample_data = json.dumps({"part_list": "PL", "rows": [
			{"source_row": "M", "color_doctype": "P-Natural", "color": "Walnut"},
		]})
		self.frappe.get_meta = Mock(return_value=SimpleNamespace(istable=False, issingle=False))
		self.frappe.db.exists.return_value = True
		config = {"rows": [{"source_row": "M", "color_doctype": "P-Natural", "color": "Oak"}]}
		with patch.object(api, "get_part_list_colors", return_value=config):
			api.validate_colors(SimpleNamespace(items=[item]))
		self.assertEqual(json.loads(item.custom_color_sample_data)["rows"][0]["color"], "Walnut")
		for name in ("custom_wood", "custom_metal", "custom_wood_color_doctype"):
			self.assertNotIn(name, item)

	def test_export_has_no_removed_fields_or_layout_references(self):
		data = json.loads((ROOT / "c4factory/c4factory/custom/sales_order_item.json").read_text())
		removed = {"custom_wood", "custom_metal", "custom_wood_color_doctype"}
		for field in data["custom_fields"]:
			self.assertNotIn(field["fieldname"], removed)
			self.assertNotIn(field.get("insert_after"), removed)
		for setter in data["property_setters"]:
			if setter["property"] == "field_order":
				self.assertFalse(removed.intersection(json.loads(setter["value"])))

	def test_migration_removes_only_header_controls_and_repairs_layout(self):
		api = load_module("c4factory/patches/v1_0/remove_sales_order_header_colors.py", "cleanup_patch")
		fields = [
			Doc(name="wood", fieldname="custom_wood", insert_after="section"),
			Doc(name="metal", fieldname="custom_metal", insert_after="custom_wood"),
			Doc(name="notes", fieldname="additional_notes", insert_after="custom_metal"),
		]
		setter = Doc(name="layout", field_name=None, property="field_order",
			value=json.dumps(["section", "custom_wood", "custom_metal", "additional_notes"]))
		self.frappe.get_all = Mock(side_effect=[fields, [setter], [], []])
		self.frappe.delete_doc = Mock()
		self.frappe.clear_cache = Mock()
		api.execute()
		self.frappe.db.set_value.assert_any_call("Custom Field", "notes", "insert_after", "section")
		self.assertEqual([call.args for call in self.frappe.delete_doc.call_args_list],
			[("Custom Field", "wood"), ("Custom Field", "metal")])
		self.frappe.delete_doc.reset_mock()
		api.execute()
		self.frappe.delete_doc.assert_not_called()


if __name__ == "__main__":
	unittest.main()
