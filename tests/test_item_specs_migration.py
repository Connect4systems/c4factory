"""Upgrades preserve site layouts, historical values, and unambiguous sources."""

import json
import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module
from test_pds_duplicates import Doc


class TestItemSpecsMigration(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe.db = Mock()
		self.frappe.get_all = Mock()
		self.frappe.get_all.return_value = []
		self.frappe.delete_doc = Mock()
		self.frappe.get_meta = Mock()
		self.frappe.clear_cache = Mock()
		custom_field = ModuleType("frappe.custom.doctype.custom_field.custom_field")
		custom_field.create_custom_fields = Mock()
		property_setter = ModuleType("frappe.custom.doctype.property_setter.property_setter")
		property_setter.make_property_setter = Mock()
		self.make_setter = property_setter.make_property_setter
		self.create_fields = custom_field.create_custom_fields
		modules = patch.dict(sys.modules, {"frappe": self.frappe, custom_field.__name__: custom_field,
			property_setter.__name__: property_setter})
		modules.start()
		self.addCleanup(modules.stop)
		self.api = load_module("c4factory/patches/v1_0/setup_item_specs.py", "item_specs_migration_test")

	def test_setup_repairs_custom_field_order_and_hides_old_controls(self):
		layouts = {}
		for dt, prefix in (("Sales Order Item", "custom_"), ("PDS Request Item", ""), ("Part List", ""), ("Project BOQ Item", "")):
			layouts[dt] = ["item", "site_field", prefix + "leather", prefix + "spcs_tab",
				*[f["fieldname"] for f in self.api.spec_layout(prefix)]]
		layouts["PDS Request Item"] += ["direction", "additional_notes", "spec_notes_section"]
		self.frappe.get_meta.side_effect = lambda dt, **kwargs: Doc(fields=[Doc(fieldname=name) for name in layouts[dt]])
		self.api.setup_fields()
		self.api.setup_fields()
		for dt, prefix in (("Sales Order Item", "custom_"), ("PDS Request Item", ""), ("Part List", ""), ("Project BOQ Item", "")):
			orders = [json.loads(call.args[3]) for call in self.make_setter.call_args_list
				if call.args[0] == dt and call.args[2] == "field_order"]
			self.assertEqual(orders[0], orders[1])
			self.assertEqual(orders[0].count("site_field"), 1)
			layout = [f["fieldname"] for f in self.api.spec_layout(prefix, tabbed=dt == "Part List")]
			self.assertEqual(orders[0][-len(layout):], layout)
			if dt != "Part List":
				self.assertNotIn(prefix + "spcs_tab", orders[0])
			if dt == "PDS Request Item":
				self.assertEqual(orders[0][-9:-6], ["spec_notes_section", "direction", "additional_notes"])
		self.make_setter.assert_any_call("Sales Order Item", "custom_leather", "hidden", 1, "Check")
		self.make_setter.assert_any_call("PDS Request Item", "leather", "reqd", 0, "Check")
		self.assertEqual(self.create_fields.call_args.kwargs, {"update": True})
		self.frappe.delete_doc.assert_any_call("Custom Field", "Sales Order Item-custom_spcs_tab", ignore_permissions=True)
		self.assertFalse(any(f["fieldtype"] == "Tab Break" for f in self.create_fields.call_args.args[0]["Sales Order Item"]))

	def test_removed_field_columns_are_migrated_even_without_metadata(self):
		self.frappe.db.has_column.return_value = True
		row = Doc(name="ROW", custom_wood="Legacy oak", custom_other_specs="Keep user text", custom_other="Old")
		self.frappe.db.sql.return_value = [row]
		self.api.migrate_legacy("Sales Order Item", "custom_")
		self.assertIn("`custom_wood`", self.frappe.db.sql.call_args.args[0])
		self.frappe.db.set_value.assert_called_once_with("Sales Order Item", "ROW",
			{"custom_panel_specs": "Wood: Legacy oak"}, update_modified=False)

	def test_backfill_preserves_edits_and_skips_ambiguous_part_lists(self):
		r1 = Doc(name="R1", parent="SO", item_code="A", custom_part_list="SHARED", custom_panel_specs="Oak", custom_metal_specs="Steel")
		r2 = Doc(name="R2", parent="SO", item_code="A", custom_part_list="SHARED", custom_panel_specs="Walnut")
		r3 = Doc(name="R3", parent="SO", item_code="B", custom_part_list="UNIQUE", custom_panel_specs="Birch")
		request_rows = [Doc(name="Q1", parent="REQ", item="A", sales_order_item="R2", part_list="FROM-PDS", panel_specs="PDS edit"),
			Doc(name="Q2", parent="REQ", item="A", sales_order_item=None, part_list=None),
			Doc(name="Q3", parent="REQ", item="B", sales_order_item=None, part_list=None)]
		parts = [Doc(name="SHARED", product="A"), Doc(name="UNIQUE", product="B", panel_specs="Part List edit"),
			Doc(name="FROM-PDS", product="A")]
		boq = Doc(name="BOQ-1", sales_order_item="R1", item_code="A")
		records = {"Sales Order Item": [r1, r2, r3], "PDS Request": [Doc(name="REQ", sales_order="SO")],
			"PDS Request Item": request_rows, "Part List": parts, "Project BOQ Item": [boq]}
		self.frappe.get_all.side_effect = lambda dt, **kwargs: records[dt]
		def update(dt, name, values, **kwargs):
			next(row for row in records[dt] if row.name == name).update(values)
		self.frappe.db.set_value.side_effect = update
		self.api.backfill_links()
		self.api.backfill_links()
		self.assertEqual(request_rows[0].panel_specs, "PDS edit")
		self.assertIsNone(request_rows[1].panel_specs)
		self.assertIsNone(request_rows[1].sales_order_item)
		self.assertEqual(request_rows[2].sales_order_item, "R3")
		self.assertIsNone(parts[0].sales_order_item)
		self.assertEqual(parts[1].panel_specs, "Part List edit")
		self.assertEqual(parts[1].sales_order_item, "R3")
		self.assertEqual(parts[2].panel_specs, "Walnut")
		self.assertEqual(parts[2].sales_order_item, "R2")
		self.assertEqual(boq.panel_specs, "Oak")
