import copy
import json
import unittest
from unittest.mock import Mock, patch

from c4factory.api import color_sample as api


class Doc(dict):
    def __getattribute__(self, key):
        if key in self:
            return dict.__getitem__(self, key)
        return dict.__getattribute__(self, key)

    def __setattr__(self, key, value):
        self[key] = value


class TestColorsample(unittest.TestCase):
    def setUp(self):
        self.source = Doc(name="SO-ROW-1", item_code="Desk", item_name="Desk", qty=10, uom="Nos")
        self.order = Doc(name="SO", docstatus=1, project="PROJECT", items=[self.source])
        self.colors = {
            "custom_part_list": "PL", "custom_wood": "Oak", "custom_metal": "Black",
            "custom_wood_color_doctype": "P-Wood",
            "custom_color_sample_data": json.dumps({"part_list": "PL", "rows": []}),
        }

    def sample(self, *quantities):
        return Doc(name="SAMPLE", sales_order="SO", items=[
            Doc(idx=i + 1, sales_order_item=self.source.name, qty=qty, **self.colors)
            for i, qty in enumerate(quantities)
        ])

    def validate(self, sample, used=0, lock=False):
        with patch.object(api, "get_order", return_value=self.order), patch.object(
            api, "submitted_quantities", return_value={self.source.name: used}
        ), patch.object(api, "source_colors", return_value=self.colors), patch.object(
            api, "validate_colors"
        ), patch.object(api.frappe, "throw", side_effect=ValueError), patch.object(
            api.frappe.db, "sql", return_value=[]
        ) as sql:
            api.validate_sample(sample, lock=lock)
            return sql

    def test_partial_quantity_and_project_are_fetched(self):
        sample = self.sample(3)
        self.validate(sample, used=4)
        self.assertEqual(sample.project, "PROJECT")
        self.assertEqual(sample.items[0].remaining_qty, 6)
        self.assertEqual(sample.items[0].order_qty, 10)
        self.assertEqual(sample.items[0].item_code, "Desk")

    def test_aggregate_duplicate_rows_cannot_exceed_balance(self):
        with self.assertRaises(ValueError):
            self.validate(self.sample(4, 3), used=4)

    def test_exact_remaining_balance_is_allowed(self):
        self.validate(self.sample(6), used=4)

    def test_invalid_quantities_are_rejected(self):
        for qty in (0, -1, float("nan"), float("inf")):
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                self.validate(self.sample(qty))

    def test_exhausted_balance_rejects_another_draft(self):
        with self.assertRaises(ValueError):
            self.validate(self.sample(1), used=10)

    def test_submission_locks_order_before_balance_check(self):
        sql = self.validate(self.sample(1), lock=True)
        self.assertIn("for update", sql.call_args.args[0])
        self.assertEqual(sql.call_args.args[1], "SO")

    def test_foreign_order_row_is_rejected(self):
        sample = self.sample(1)
        sample.items[0].sales_order_item = "OTHER-ORDER-ROW"
        with self.assertRaises(ValueError):
            self.validate(sample)

    def test_only_submitted_samples_consume_quantity(self):
        with patch.object(api.frappe.db, "sql", return_value=[Doc(sales_order_item="ROW", qty=3)]) as sql:
            self.assertEqual(api.submitted_quantities("SO", "CURRENT"), {"ROW": 3})
        self.assertIn("s.docstatus = 1", sql.call_args.args[0])
        self.assertEqual(sql.call_args.args[1], {"sales_order": "SO", "exclude": "CURRENT"})

    def test_submission_uses_current_read_and_sums_multiple_samples(self):
        with patch.object(api.frappe.db, "sql", return_value=[
            Doc(sales_order_item="ROW", qty=2), Doc(sales_order_item="ROW", qty=3)
        ]) as sql:
            self.assertEqual(api.submitted_quantities("SO", lock=True), {"ROW": 5})
        self.assertTrue(sql.call_args.args[0].endswith(" for update"))

    def test_inherits_order_colors_without_changing_source_part_list(self):
        config = {"wood_color": "Standard", "wood_color_doctype": "P-Wood",
                  "metal_color": "Black", "rows": [
                      {"source_row": "M", "color_doctype": "P-Wood", "color": "Standard"}
                  ]}
        self.source.custom_part_list = "PL"
        self.source.custom_wood = "Order Override"
        self.source.custom_color_sample_data = json.dumps({"part_list": "PL", "rows": [
            {"source_row": "M", "color_doctype": "P-Wood", "color": "Row Override"}
        ]})
        before = dict(self.source)
        with patch.object(api, "get_part_list_colors", side_effect=lambda name: copy.deepcopy(config)):
            result = api.source_colors(self.source)
        self.assertEqual(result["custom_wood"], "Order Override")
        self.assertEqual(json.loads(result["custom_color_sample_data"])["rows"][0]["color"], "Row Override")
        self.assertEqual(config["rows"][0]["color"], "Standard")
        self.assertEqual(dict(self.source), before)

    def test_create_requires_submitted_sales_order(self):
        self.order.docstatus = 0
        self.order.check_permission = Mock()
        with patch.object(api.frappe, "get_doc", return_value=self.order), patch.object(
            api.frappe, "throw", side_effect=ValueError
        ), self.assertRaises(ValueError):
            api.get_order("SO")

    def test_noneditable_material_rejects_individual_override(self):
        source = {"source_row": "M", "source_table": "other_material", "edite_color": 0,
                  "color": "Standard", "material": "Fabric"}
        self.colors["custom_color_sample_data"] = json.dumps({"part_list": "PL", "rows": [source]})
        sample = self.sample(1)
        changed = dict(source, color="Changed")
        sample.items[0].custom_color_sample_data = json.dumps({"part_list": "PL", "rows": [changed]})
        with self.assertRaises(ValueError):
            self.validate(sample)
