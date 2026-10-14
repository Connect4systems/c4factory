"""Production quantity and design snapshot checks without a local bench."""

import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from test_part_list_save import ROOT, load_module


class Doc(dict):
	def __getattribute__(self, key):
		if key in self:
			return dict.__getitem__(self, key)
		return dict.__getattribute__(self, key)

	def __setattr__(self, key, value):
		self[key] = value

	def set(self, key, value):
		if key in api_tables and value:
			value = [child(row, child_fields[key]) for row in value]
		self[key] = value

	def get_doc_before_save(self):
		return self.get("previous")


api_tables = ("pds_table", "panel_materials", "metal_material", "other_material", "accessorise_table")
child_fields = {
	"pds_table": ["title", "arttach"],
	"accessorise_table": ["item", "qty"],
}
for key in ("panel_materials", "metal_material", "other_material"):
	child_fields[key] = ["material", "part_name", "qty", "basic_color", "color_doctype", "edite_color"]


def child(values, fields):
	return Doc(**values, meta=SimpleNamespace(fields=[SimpleNamespace(fieldname=f, fieldtype="Data") for f in fields]))


class TestProductionOrder(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe._ = lambda value: value
		self.frappe.whitelist = lambda: lambda fn: fn
		self.frappe.throw = Mock(side_effect=ValueError)
		self.frappe.db = Mock()
		self.frappe.db.sql.return_value = []
		utils = ModuleType("frappe.utils")
		utils.flt = lambda value: float(value or 0)
		utils.cint = lambda value: int(value or 0)
		utils.today = lambda: "2026-10-14"
		utils.now_datetime = lambda: "NOW"
		self.row = Doc(name="SAMPLE-ROW", item_code="DESK", item_name="Desk", qty=10, uom="Nos",
			custom_part_list="PL", custom_color_sample_data=json.dumps({"part_list": "PL", "rows": [
				{"source_row": "MATERIAL", "color_doctype": "P-Wood", "color": "Blue"},
			]}))
		self.sample = Doc(name="SAMPLE", docstatus=1, project="PROJECT", sales_order="SO", items=[self.row], check_permission=Mock())
		self.part = Doc(name="PL", product="DESK", product_name="Desk", docstatus=1, check_permission=Mock(),
			width=100, hight=70, depth=60, description="Design", material_line="LINE", metal_material_line="LINE")
		self.part.panel_materials = [child({"name": "MATERIAL", "material": "Wood", "qty": 2,
			"color_doctype": "P-Wood", "basic_color": "Red", "edite_color": 1}, child_fields["panel_materials"])]
		self.part.pds_table = [child({"name": "PDS", "title": "Drawing", "arttach": "/private/files/design.pdf"}, child_fields["pds_table"])]
		self.part.accessorise_table = [child({"name": "ACCESSORY", "item": "Pin", "qty": 4}, child_fields["accessorise_table"])]
		self.part.metal_material = []
		self.part.other_material = []
		schema = json.loads((ROOT / "c4factory/c4factory/doctype/part_list/part_list.json").read_text())
		self.part.meta = SimpleNamespace(fields=[SimpleNamespace(**f) for f in schema["fields"]])
		self.frappe.get_doc = Mock(side_effect=lambda doctype, name: self.sample if doctype == "Color sample" else self.part)
		modules = {"frappe": self.frappe, "frappe.utils": utils}
		with patch.dict(sys.modules, modules):
			versions = load_module("c4factory/api/part_list_versions.py", "production_copy_test")
			with patch.dict(sys.modules, {"c4factory.api.part_list_versions": versions}):
				self.api = load_module("c4factory/api/production_order.py", "production_order_test")
		self.order = Doc(name="PO-DESK-01", color_sample="SAMPLE", color_sample_item="SAMPLE-ROW", product="DESK", qty=4)

	def test_partial_order_leaves_balance_for_future_order(self):
		self.frappe.db.sql.return_value = [Doc(color_sample_item="SAMPLE-ROW", qty=3)]
		self.api.validate_order(self.order)
		self.assertEqual(self.order.sample_qty, 10)
		self.assertEqual(self.order.ordered_qty, 3)
		self.assertEqual(self.order.remaining_qty, 3)
		available = self.api.get_available_items("SAMPLE")
		self.assertEqual(available[0]["remaining_qty"], 7)

	def test_overallocation_and_invalid_quantities_rejected(self):
		for qty in (11, 0, -1, float("nan"), float("inf")):
			self.order.qty = qty
			with self.subTest(qty=qty), self.assertRaises(ValueError):
				self.api.validate_order(self.order)

	def test_full_quantity_and_multiple_previous_orders(self):
		self.frappe.db.sql.return_value = [Doc(color_sample_item="SAMPLE-ROW", qty=2),
			Doc(color_sample_item="SAMPLE-ROW", qty=4), Doc(color_sample_item="OTHER", qty=99)]
		self.api.validate_order(self.order)
		self.assertEqual(self.order.remaining_qty, 0)

	def test_submit_locks_sample_and_reads_current_orders(self):
		self.frappe.db.sql.side_effect = [[Doc(docstatus=1)], []]
		self.api.validate_order(self.order, lock=True)
		calls = self.frappe.db.sql.call_args_list
		self.assertIn("tabColor sample", calls[0].args[0])
		self.assertIn("for update", calls[0].args[0])
		self.assertIn("for update", calls[1].args[0])
		self.assertIn("docstatus = 1", calls[1].args[0])
		self.assertEqual(calls[1].args[1]["exclude"], "PO-DESK-01")

	def test_competing_submission_rechecked_after_balance_consumed(self):
		self.frappe.db.sql.side_effect = [[Doc(docstatus=1)], []]
		self.api.validate_order(self.order, lock=True)
		self.frappe.db.sql.side_effect = [[Doc(docstatus=1)], [Doc(color_sample_item="SAMPLE-ROW", qty=8)]]
		with self.assertRaises(ValueError):
			self.api.validate_order(self.order, lock=True)

	def test_submit_rejects_sample_cancelled_after_draft_validation(self):
		self.api.validate_order(self.order)
		self.frappe.db.sql.side_effect = [[Doc(docstatus=2)]]
		with self.assertRaises(ValueError):
			self.api.validate_order(self.order, lock=True)

	def test_draft_and_cancelled_samples_rejected(self):
		for status in (0, 2):
			self.sample.docstatus = status
			with self.subTest(status=status), self.assertRaises(ValueError):
				self.api.validate_order(self.order)

	def test_snapshot_copies_all_tables_and_applies_sample_color(self):
		values = self.api.snapshot_values(self.row)
		self.assertEqual(values["panel_materials"][0]["basic_color"], "Blue")
		self.assertEqual(values["panel_materials"][0]["qty"], 2)
		self.assertNotIn("name", values["panel_materials"][0])
		self.assertEqual(values["pds_table"][0]["arttach"], "/private/files/design.pdf")
		self.assertEqual(values["accessorise_table"][0]["qty"], 4)
		self.assertEqual(values["width"], 100)
		self.assertEqual(self.part.panel_materials[0].basic_color, "Red")
		self.assertTrue(set(api_tables).issubset(values))

	def test_prepare_fetches_links_and_ignores_spoofed_product(self):
		self.order.product = "WRONG"
		self.api.prepare_order(self.order)
		self.assertEqual(self.order.product, "DESK")
		self.assertEqual(self.order.sales_order, "SO")
		self.assertEqual(self.order.project, "PROJECT")
		self.assertEqual(self.order.part_list, "PL")
		self.assertEqual(self.order.panel_materials[0].basic_color, "Blue")

	def test_existing_snapshot_survives_source_part_list_changes(self):
		self.api.prepare_order(self.order)
		previous = Doc(self.order)
		self.order.previous = previous
		self.part.width = 500
		self.part.panel_materials[0].basic_color = "Green"
		self.api.prepare_order(self.order)
		self.assertEqual(self.order.width, 100)
		self.assertEqual(self.order.panel_materials[0].basic_color, "Blue")

	def test_existing_order_cannot_retarget_sample_or_change_design(self):
		self.api.prepare_order(self.order)
		self.order.previous = Doc(self.order)
		self.order.meta = SimpleNamespace(get_label=lambda field: field)
		self.order.width = 999
		with self.assertRaises(ValueError):
			self.api.prepare_order(self.order)

	def test_sample_cancel_blocked_only_by_submitted_orders(self):
		self.frappe.db.sql.side_effect = [[], [("PO",)]]
		with self.assertRaises(ValueError):
			self.api.prevent_sample_cancel(self.sample)
		self.assertIn("docstatus = 1", self.frappe.db.sql.call_args.args[0])
		self.assertIn("for update", self.frappe.db.sql.call_args.args[0])
		self.frappe.db.sql.side_effect = [[], []]
		self.api.prevent_sample_cancel(self.sample)

	def test_naming_uses_product_code_and_two_digits(self):
		naming = ModuleType("frappe.model.naming")
		naming.getseries = Mock(return_value="01")
		document = ModuleType("frappe.model.document")
		document.Document = type("Document", (), {})
		with patch.dict(sys.modules, {"frappe": self.frappe, "frappe.model.naming": naming,
			"frappe.model.document": document, "c4factory.api.production_order": self.api}):
			controller = load_module("c4factory/c4factory/doctype/production_order/production_order.py", "production_controller_test")
			controller.ProductionOrder.autoname(self.order)
		self.assertEqual(self.order.name, "PO-DESK-01")
		naming.getseries.assert_called_once_with("PO-DESK-", 2)

	def test_schema_has_all_part_list_snapshot_fields_and_tables(self):
		schema = json.loads((ROOT / "c4factory/c4factory/doctype/production_order/production_order.json").read_text())
		fields = {field["fieldname"]: field for field in schema["fields"]}
		self.assertTrue(set(self.api.SNAPSHOT_FIELDS).issubset(fields))
		self.assertEqual(set(schema["field_order"]), set(fields))
		for field in self.api.TABLE_FIELDS:
			self.assertEqual(fields[field]["fieldtype"], "Table")
			self.assertTrue(fields[field]["read_only"])


if __name__ == "__main__":
	unittest.main()
