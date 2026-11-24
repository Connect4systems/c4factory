"""Transaction progress and validation checks runnable without a Frappe bench."""

import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module


class Doc(dict):
	def __getattr__(self, key):
		return self.get(key)

	def __setattr__(self, key, value):
		self[key] = value

	@property
	def items(self):
		return self.get("items", [])


class TestProjectBOQ(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe._ = lambda value: value
		self.frappe.whitelist = lambda: lambda fn: fn
		self.frappe.throw = Mock(side_effect=ValueError)
		self.frappe.db = Mock()
		self.frappe.get_doc = Mock()
		self.frappe.get_all = Mock(return_value=["A"])
		self.frappe.get_all.side_effect = lambda *args, **kwargs: self.frappe.get_all.return_value if kwargs.get("pluck") else [Doc(name="A", image="/files/a.png")]
		self.frappe.parse_json = __import__("json").loads
		utils = ModuleType("frappe.utils")
		utils.flt = lambda value: float(value or 0)
		utils.today = lambda: "2026-11-20"
		boq = ModuleType("c4factory.api.boq_items")
		boq.boq_item_filters = lambda: {"custom_item_type": "BOQ"}
		modules = patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": utils,
			"c4factory.api.boq_items": boq})
		modules.start()
		self.addCleanup(modules.stop)
		self.api = load_module("c4factory/api/project_boq.py", "project_boq_test")

	def test_partial_delivery_can_be_fully_installed(self):
		self.assertEqual(self.api.progress_status(10, 4, 4), ("Partly Delivered", "Fully Installed"))
		self.assertEqual(self.api.progress_status(10, 0, 0), ("Not Delivered", "Not Delivered"))
		self.assertEqual(self.api.progress_status(10, 4, 2), ("Partly Delivered", "Partly Installed"))

	def test_existing_project_resolves_sales_order_reverse_link(self):
		self.frappe.get_all.return_value = ["SO-OLD"]
		project = Doc(name="P-OLD")
		self.assertEqual(self.api.resolve_sales_order(project), "SO-OLD")
		self.assertEqual(project.sales_order, "SO-OLD")
		self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"], {"project": "P-OLD", "docstatus": 1})

	def test_ambiguous_reverse_link_requires_explicit_order(self):
		self.frappe.get_all.return_value = ["SO-1", "SO-2"]
		with self.assertRaises(ValueError):
			self.api.resolve_sales_order(Doc(name="P"))

	def test_fetch_returns_rows_and_status_for_legacy_project(self):
		project = Doc(name="P", check_permission=Mock())
		order = Doc(name="SO", docstatus=1, status="To Deliver", check_permission=Mock())
		self.frappe.get_all.return_value = ["SO"]
		self.frappe.get_doc.side_effect = [project, order]
		rows = [{"item_code": "A", "pds_status": "PDS Request: REQ", "delivered_qty": 2}]
		with patch.object(self.api, "build_rows", return_value=rows):
			result = self.api.get_project_boq("P")
		self.assertEqual(result, {"rows": rows, "sales_order": "SO", "active": True})
		project.check_permission.assert_called_once_with("read")
		order.check_permission.assert_called_once_with("read")

	def test_no_source_returns_empty_result_without_active_actions(self):
		self.frappe.get_all.return_value = []
		self.frappe.get_doc.return_value = Doc(name="P", check_permission=Mock())
		self.assertEqual(self.api.get_project_boq("P"), {"rows": [], "sales_order": None, "active": False})

	def test_selection_rejects_invalid_quantities_and_duplicates(self):
		for rows in ([], [{"sales_order_item": "R", "qty": -1}],
			[{"sales_order_item": "R", "qty": float("inf")}],
			[{"sales_order_item": "R", "qty": 1}] * 2):
			with self.subTest(rows=rows), self.assertRaises(ValueError):
				self.api.selections(rows)

	def test_repeated_item_rows_remain_separate_and_returns_use_stock_uom(self):
		order = Doc(name="SO", items=[Doc(name=name, item_code="A", item_name="Item", qty=5,
			description=name, uom="Box", conversion_factor=2, custom_panel_specs="Panel " + name,
			custom_metal_specs="Metal " + name, custom_other_specs="Other " + name) for name in ("R1", "R2")])
		self.frappe.get_doc.return_value = order
		self.frappe.db.sql.return_value = []
		self.frappe.db.exists.return_value = False
		deliveries = [Doc(name="D1", so_detail="R1", stock_qty=8, conversion_factor=2, is_return=0),
			Doc(name="RET", so_detail="R1", stock_qty=-2, is_return=1)]
		with patch.object(self.api, "delivery_rows", return_value=deliveries), patch.object(
			self.api, "installed_quantities", return_value={"D1": 2}):
			rows = self.api.build_rows(Doc(sales_order="SO"))
		self.assertEqual([r["sales_order_item"] for r in rows], ["R1", "R2"])
		self.assertEqual(rows[0]["delivered_qty"], 3)
		self.assertEqual(rows[0]["installed_qty"], 2)
		self.assertEqual(rows[1]["delivered_qty"], 0)
		self.assertEqual(rows[0]["description"], "R1")
		self.assertEqual([r["panel_specs"] for r in rows], ["Panel R1", "Panel R2"])
		self.assertEqual([r["metal_specs"] for r in rows], ["Metal R1", "Metal R2"])
		self.assertEqual([r["other_specs"] for r in rows], ["Other R1", "Other R2"])

	def test_boq_preserves_edited_and_cleared_notes_by_source_row(self):
		order = Doc(name="SO", items=[Doc(name=name, item_code="A", item_name="Item", qty=1,
			description=name, uom="Nos", custom_note="Quotation " + name) for name in ("R1", "R2", "R3")])
		self.frappe.get_doc.return_value = order
		self.frappe.db.sql.return_value = []
		project = Doc(sales_order="SO", custom_project_boq=[
			Doc(sales_order_item="R1", note="Edited", note_initialized=1),
			Doc(sales_order_item="R2", note="", note_initialized=1)])
		with patch.object(self.api, "delivery_rows", return_value=[]):
			rows = self.api.build_rows(project)
		self.assertEqual([r["note"] for r in rows], ["Edited", "", "Quotation R3"])
		self.assertTrue(all(r["image"] == "/files/a.png" for r in rows))

	def test_submitted_part_list_takes_precedence_over_request(self):
		self.frappe.get_doc.return_value = Doc(name="SO", items=[Doc(name="R", item_code="A",
			item_name="Item", qty=1, uom="Nos", custom_part_list="PL")])
		self.frappe.db.exists.return_value = "PL"
		self.frappe.db.sql.return_value = [Doc(item="A", sales_order_item="R", sales_order="SO", parent="REQ")]
		with patch.object(self.api, "delivery_rows", return_value=[]):
			rows = self.api.build_rows(Doc(sales_order="SO"))
		self.assertEqual(rows[0]["pds_status"], "PDS: PL")
		self.assertEqual(self.frappe.db.exists.call_args.args[1]["docstatus"], 1)

	def test_cancelled_order_blocks_actions(self):
		project = Doc(sales_order="SO", check_permission=Mock())
		order = Doc(name="SO", docstatus=2, check_permission=Mock())
		self.frappe.get_doc.side_effect = [project, order]
		with self.assertRaises(ValueError):
			self.api.active_order("P")

	def test_duplicate_drafts_are_rejected(self):
		self.frappe.db.sql.return_value = [("DN-DRAFT",)]
		self.frappe.has_permission = Mock(return_value=True)
		with self.assertRaises(ValueError):
			self.api.draft_conflicts("Delivery Note", "SO", ["R"])
		self.assertIn("DN-DRAFT", self.frappe.throw.call_args.args[0])

	def test_duplicate_installation_rows_cannot_exceed_delivery(self):
		source = Doc(name="D", parent="DN", qty=5, item_code="A")
		parent = Doc(name="DN", docstatus=1, is_return=0, customer="C", company="CO")
		self.frappe.get_doc.side_effect = lambda dt, name: source if dt == "Delivery Note Item" else parent
		doc = Doc(name="INS", customer="C", company="CO", items=[Doc(
			prevdoc_detail_docname="D", prevdoc_docname="DN", item_code="A", qty=3)] * 2)
		with patch.object(self.api, "installed_quantities", return_value={}), patch.object(
			self.api, "returned_qty", return_value=0), self.assertRaises(ValueError):
			self.api.validate_installation(doc)

	def test_installed_delivery_cannot_be_cancelled(self):
		doc = Doc(items=[Doc(name="D", against_sales_order="SO")])
		with patch.object(self.api, "installed_quantities", return_value={"D": 1}), self.assertRaises(ValueError):
			self.api.guard_delivery_change(doc, "before_cancel")

	def test_return_cancellation_does_not_remove_delivered_units(self):
		self.api.guard_delivery_change(Doc(is_return=1), "before_cancel")
		self.frappe.db.sql.assert_not_called()

	def test_delivery_draft_contains_only_selected_rows_and_partial_qty(self):
		target = Mock()
		target.name = "DN-DRAFT"
		target.items = [Doc(so_detail="R1", qty=10), Doc(so_detail="R2", qty=10)]
		target.set.side_effect = lambda key, value: setattr(target, key, value)
		mapper = ModuleType("erpnext.selling.doctype.sales_order.sales_order")
		mapper.make_delivery_note = Mock(return_value=target)
		packing = ModuleType("erpnext.stock.doctype.packed_item.packed_item")
		packing.make_packing_list = Mock()
		with patch.dict(sys.modules, {mapper.__name__: mapper, packing.__name__: packing}), patch.object(
			self.api, "active_order", return_value=(Doc(name="P"), Doc(name="SO"))), patch.object(
			self.api, "build_rows", return_value=[{"sales_order_item": "R2", "actual_qty": 10, "delivered_qty": 3}]), patch.object(
			self.api, "draft_conflicts"):
			name = self.api.create_delivery_note("P", [{"sales_order_item": "R2", "qty": 2}])
		self.assertEqual(name, "DN-DRAFT")
		self.assertEqual([(r.so_detail, r.qty, r.project) for r in target.items], [("R2", 2, "P")])
		target.insert.assert_called_once_with()
		target.submit.assert_not_called()
		packing.make_packing_list.assert_called_once_with(target)

	def test_installation_draft_preserves_delivery_row_reference(self):
		target = Mock()
		target.name = "INS-DRAFT"
		self.frappe.new_doc = Mock(return_value=target)
		self.frappe.get_doc.return_value = Doc(name="DN", check_permission=Mock(), items=[Doc(
			name="D1", item_code="A", description="Order spec")])
		with patch.object(self.api, "active_order", return_value=(Doc(name="P"), Doc(name="SO", customer="C"))), patch.object(
			self.api, "installation_options", return_value=[{"delivery_note_item": "D1", "delivery_note": "DN", "qty": 3}]), patch.object(
			self.api, "draft_conflicts"):
			name = self.api.create_installation_note("P", "R1", [{"sales_order_item": "D1", "qty": 2}])
		self.assertEqual(name, "INS-DRAFT")
		row = target.append.call_args.args[1]
		self.assertEqual(row["prevdoc_detail_docname"], "D1")
		self.assertEqual(row["prevdoc_docname"], "DN")
		self.assertEqual(row["qty"], 2)
		target.insert.assert_called_once_with()
		target.submit.assert_not_called()


if __name__ == "__main__":
	unittest.main()
