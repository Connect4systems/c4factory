"""Technical's table permissions govern sample base colors and material rows."""
import copy
import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from test_material_palettes import ColorDoc
from test_part_list_save import ROOT, load_module
from test_project_boq import Doc


class TestSampleBaseColors(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda value: value
        self.frappe.whitelist = lambda: lambda fn: fn
        self.frappe.validate_and_sanitize_search_inputs = lambda fn: fn
        self.frappe.throw = Mock(side_effect=ValueError)
        self.frappe.db = Mock()
        self.frappe.db.exists.side_effect = lambda dt, filters: filters["name"] in {"Oak", "Walnut", "Steel"} and (
            filters["palette"] == ("Metal" if filters["name"] == "Steel" else "Wood"))
        self.frappe.db.get_value.return_value = 0
        self.frappe.get_doc = Mock()
        with patch.dict(sys.modules, {"frappe": self.frappe}):
            materials = load_module("c4factory/api/part_list_material_colors.py", "base_materials_test")
            with patch.dict(sys.modules, {"c4factory.api.part_list_material_colors": materials}):
                self.api = load_module("c4factory/api/sales_order_colors.py", "base_order_colors_test")
        self.config = {
            "base_colors": [
                dict(source_table="panel_materials", color_palette="Wood", color="Oak", allow_edit=True),
                dict(source_table="metal_material", color_palette="Metal", color="Steel", allow_edit=False)],
            "rows": [dict(source_row="P1", source_table="panel_materials", color_palette="Wood", material="Wood",
                color_doctype="Material Color", color="Oak", edite_color=0),
                dict(source_row="M1", source_table="metal_material", color_palette="Metal", material="Metal",
                color_doctype="Material Color", color="Steel", edite_color=0)]}

    def stored(self, color="Walnut"):
        data = copy.deepcopy(self.config)
        data["part_list"] = "PL"
        data["base_colors"][0]["color"] = color
        return data

    def validate(self, stored, doctype="Color Sample Item"):
        item = ColorDoc(doctype=doctype, idx=1, custom_part_list="PL", meta=Mock(),
            custom_color_sample_data=json.dumps(stored))
        with patch.object(self.api, "get_part_list_colors", return_value=copy.deepcopy(self.config)):
            self.api.validate_colors(SimpleNamespace(items=[item]))
        return json.loads(item.custom_color_sample_data)

    def test_enabled_base_changes_all_table_rows_without_affecting_other_tables(self):
        data = self.validate(self.stored())
        self.assertEqual([r["color"] for r in data["rows"]], ["Walnut", "Steel"])
        self.assertEqual(self.validate(data), data)
        self.assertEqual(self.config["rows"][0]["color"], "Oak")

    def test_locked_checkbox_cannot_be_forged_in_client_data(self):
        self.config["base_colors"][0]["allow_edit"] = False
        data = self.stored()
        data["base_colors"][0]["allow_edit"] = True
        with self.assertRaises(ValueError):
            self.validate(data)

    def test_wrong_palette_and_disabled_colors_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(self.stored("Steel"))
        self.frappe.db.get_value.return_value = 1
        with self.assertRaises(ValueError):
            self.validate(self.stored())

    def test_individual_color_edit_remains_available_after_base_selection(self):
        self.config["rows"][0]["edite_color"] = 1
        data = self.stored()
        data["rows"][0]["color"] = "Oak"
        self.assertEqual(self.validate(data)["rows"][0]["color"], "Oak")

    def test_sales_order_does_not_gain_base_override_permission(self):
        data = self.validate(self.stored(), doctype="Sales Order Item")
        self.assertEqual(data["base_colors"][0]["color"], "Oak")
        self.assertEqual(data["rows"][0]["color"], "Oak")

    def test_old_samples_without_base_selections_keep_their_defaults(self):
        data = self.stored()
        del data["base_colors"]
        self.assertEqual(self.validate(data)["rows"][0]["color"], "Oak")

    def test_empty_color_materials_still_included_for_base_selection(self):
        part = ColorDoc(panel_materials=[ColorDoc(name="P", part_name="Top", color_palette="Wood",
            basic_color=None, edite_color=0)], panel_allow_edit=1, panel_color_palette="Wood",
            panel_base_color=None, check_permission=Mock())
        self.frappe.get_doc.return_value = part
        data = self.api.get_part_list_colors("PL")
        self.assertEqual(data["rows"][0]["source_row"], "P")
        self.assertTrue(data["base_colors"][0]["allow_edit"])
        self.assertFalse(data["base_colors"][1]["allow_edit"])

    def test_checkboxes_are_in_header_row_before_each_material_table(self):
        meta = json.loads((ROOT / "c4factory/c4factory/doctype/part_list/part_list.json").read_text())
        fields = {f["fieldname"]: f for f in meta["fields"]}
        for prefix in ("panel", "metal", "other"):
            order = meta["field_order"]
            start = order.index(prefix + "_base_color")
            self.assertEqual(order[start:start + 4], [prefix + "_base_color", prefix + "_allow_edit_column",
                prefix + "_allow_edit", prefix + "_table_section"])
            self.assertEqual(fields[prefix + "_allow_edit"]["default"], "0")

    def validate_sample(self, stored):
        utils = ModuleType("frappe.utils")
        utils.flt = lambda value: float(value or 0)
        utils.today = lambda: "2026-11-23"
        with patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": utils,
                "c4factory.api.sales_order_colors": self.api}):
            sample_api = load_module("c4factory/api/color_sample.py", "base_sample_integration_test")
        item = Doc(doctype="Color Sample Item", idx=1, sales_order_item="SO-ROW", qty=1,
            meta=Mock(), custom_part_list="PL", custom_color_sample_data=json.dumps(stored))
        sample = Doc(name="SAMPLE", sales_order="SO", items=[item])
        order = Doc(name="SO", items=[Doc(name="SO-ROW", qty=2, item_code="Desk", item_name="Desk", uom="Nos")])
        baseline = {"custom_part_list": "PL", "custom_color_sample_data": json.dumps(self.stored("Oak"))}
        with patch.object(sample_api, "get_order", return_value=order), patch.object(
                sample_api, "submitted_quantities", return_value={}), patch.object(
                sample_api, "source_colors", return_value=baseline), patch.object(
                self.api, "get_part_list_colors", return_value=copy.deepcopy(self.config)):
            sample_api.validate_sample(sample)
        return json.loads(item.custom_color_sample_data)

    def test_sample_validation_accepts_enabled_base_for_noneditable_materials(self):
        data = self.validate_sample(self.stored())
        self.assertEqual(data["rows"][0]["color"], "Walnut")

    def test_sample_validation_rejects_individual_changes_when_both_permissions_off(self):
        self.config["base_colors"][0]["allow_edit"] = False
        data = self.stored("Oak")
        data["rows"][0]["color"] = "Walnut"
        data["rows"][0]["material"] = "Wood"
        with self.assertRaises(ValueError):
            self.validate_sample(data)
