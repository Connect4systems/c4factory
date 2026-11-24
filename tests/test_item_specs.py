"""Specifications preserve exact source rows and migrate without losing edits."""

import json
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module
from test_pds_duplicates import Doc

from c4factory.api.item_specs import SPEC_FIELDS, legacy_spec_values, part_list_source_values

ROOT = Path(__file__).resolve().parents[1]


class TestItemSpecs(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe._ = lambda text: text
		self.frappe.whitelist = lambda: lambda method: method
		self.frappe.validate_and_sanitize_search_inputs = lambda method: method
		self.frappe.throw = Mock(side_effect=ValueError)
		self.frappe.db = Mock()
		self.frappe.get_doc = Mock()
		self.modules = patch.dict(sys.modules, {"frappe": self.frappe})
		self.modules.start()
		self.addCleanup(self.modules.stop)

	def test_part_list_fetches_exact_order_row_including_blank_and_multiline_text(self):
		order = Doc(name="SO", check_permission=Mock(), items=[
			Doc(name="ROW-1", item_code="A", custom_panel_specs="Wrong"),
			Doc(name="ROW-2", item_code="A", custom_panel_specs="Oak\n18mm", custom_metal_specs="", custom_other_specs="Glass"),
		])
		self.frappe.get_doc.return_value = order
		values = part_list_source_values(Doc(sales_order="SO"), Doc(item="A", sales_order_item="ROW-2", panel_specs="PDS edit"))
		self.assertEqual(values, {"sales_order": "SO", "sales_order_item": "ROW-2",
			"panel_specs": "Oak\n18mm", "metal_specs": "", "other_specs": "Glass"})
		order.check_permission.assert_called_once_with("read")

	def test_missing_wrong_or_ambiguous_order_row_is_rejected(self):
		self.frappe.get_doc.return_value = Doc(items=[Doc(name="R1", item_code="A"),
			Doc(name="R2", item_code="A"), Doc(name="R3", item_code="B")], check_permission=Mock())
		for reference in (None, "DELETED", "R3"):
			with self.subTest(reference=reference), self.assertRaises(ValueError):
				part_list_source_values(Doc(sales_order="SO"), Doc(item="A", sales_order_item=reference))

	def test_legacy_unique_product_is_safe_and_standalone_pds_uses_saved_specs(self):
		self.frappe.get_doc.return_value = Doc(name="SO", items=[Doc(name="R1", item_code="A", custom_panel_specs="Oak")], check_permission=Mock())
		values = part_list_source_values(Doc(sales_order="SO"), Doc(item="A"))
		self.assertEqual(values["sales_order_item"], "R1")
		self.assertEqual(part_list_source_values(Doc(), Doc(panel_specs="Standalone", metal_specs="Steel", other_specs="")),
			{"panel_specs": "Standalone", "metal_specs": "Steel", "other_specs": ""})

	def test_legacy_migration_is_labelled_and_repeatable_without_overwriting_text(self):
		row = Doc(custom_wood="Oak", custom_top="Veneer", custom_metal="Steel", custom_leather="Tan", custom_other="Cable tray")
		values = legacy_spec_values(row, "custom_")
		self.assertEqual(values, {"custom_panel_specs": "Wood: Oak\nTop: Veneer",
			"custom_metal_specs": "Metal: Steel", "custom_other_specs": "Leather: Tan\nOther: Cable tray"})
		row.update(values)
		self.assertEqual(legacy_spec_values(row, "custom_"), {})
		row.custom_panel_specs = "Edited"
		self.assertEqual(legacy_spec_values(row, "custom_"), {})

	def test_creation_endpoint_inserts_fetched_specs_and_keeps_source_reference(self):
		document = ModuleType("frappe.model.document")
		document.Document = object
		with patch.dict(sys.modules, {document.__name__: document}):
			controller = load_module("c4factory/c4factory/doctype/pds_request/pds_request.py", "pds_specs_controller_test")
		row = Doc(name="PDS-ROW", item="A", description="Description", image="Image", sales_order_item="SO-ROW")
		request = Doc(docstatus=0, sales_order="SO", items=[row], check_permission=Mock())
		order = Doc(name="SO", items=[Doc(name="SO-ROW", item_code="A", custom_panel_specs="Oak", custom_metal_specs="Steel", custom_other_specs="Glass")], check_permission=Mock())
		part = Mock(name="PL")
		part.name = "PL"
		self.frappe.get_doc.side_effect = [request, order, part]
		self.frappe.get_cached_doc = Mock(return_value=Doc(item_name="Product", image="Item Image"))
		self.assertEqual(controller.create_part_list_for_item("A", pds_request="PDS", pds_request_item="PDS-ROW"), "PL")
		values = self.frappe.get_doc.call_args.args[0]
		self.assertEqual(values["panel_specs"], "Oak")
		self.assertEqual(values["sales_order_item"], "SO-ROW")
		part.insert.assert_called_once_with(ignore_permissions=False)

	def test_all_four_documents_have_the_same_three_column_text_layout(self):
		for doctype in ("part_list", "pds_request_item", "project_boq_item"):
			data = json.loads((ROOT / f"c4factory/c4factory/doctype/{doctype}/{doctype}.json").read_text())
			self.check_layout(data["fields"], data["field_order"], "", doctype == "project_boq_item", doctype == "part_list")
		data = json.loads((ROOT / "c4factory/c4factory/custom/sales_order_item.json").read_text())
		order = json.loads(next(row["value"] for row in data["property_setters"] if row["property"] == "field_order"))
		self.check_layout(data["custom_fields"], order, "custom_", False)

	def check_layout(self, fields, order, prefix, read_only, tabbed=False):
		if not tabbed:
			self.assertFalse(any(field["fieldtype"] == "Tab Break" for field in fields))
		fields = {field["fieldname"]: field for field in fields}
		names = [prefix + name for name in ("spcs_section", "panel_specs", "spcs_metal_column", "metal_specs", "spcs_other_column", "other_specs")]
		if tabbed:
			names.insert(0, prefix + "spcs_tab")
			self.assertEqual(fields[names[0]]["fieldtype"], "Tab Break")
		else:
			self.assertEqual(fields[names[0]]["label"], "Spcs")
		self.assertEqual(order[-len(names):], names)
		for name, label in zip(SPEC_FIELDS, ("Panel", "Metal", "Other"), strict=True):
			field = fields[prefix + name]
			self.assertEqual((field["label"], field["fieldtype"], field.get("read_only", 0)), (label, "Text", int(read_only)))
