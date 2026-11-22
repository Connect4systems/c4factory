import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module
from test_project_boq import Doc


class Delivery(Doc):
    def set(self, field, value):
        self[field] = value


class TestDeliveryNoteDetails(unittest.TestCase):
    def setUp(self):
        frappe = ModuleType("frappe")
        frappe.db = Mock()
        self.orders = {
            "SO1": Doc(custom_project_title="Project", custom_technical_team="Team"),
            "SO2": Doc(custom_project_title="Other", custom_technical_team="Other Team"),
        }
        self.rows = {
            "R1": Doc(parent="SO1", item_code="A", custom_note="First"),
            "R2": Doc(parent="SO1", item_code="A", custom_note="Second"),
        }
        self.projects = {"PROJ-0001": "P-8716", "PROJ-0002": "P-2000"}
        frappe.db.get_value.side_effect = lambda dt, name, *a, **kw: (
            self.orders.get(name) if dt == "Sales Order" else
            self.projects.get(name) if dt == "Project" else self.rows.get(name))
        with patch.dict(sys.modules, {"frappe": frappe}):
            self.api = load_module("c4factory/api/delivery_note_details.py", "delivery_note_details_test")

    def row(self, name, **values):
        return Doc(so_detail=name, against_sales_order="SO1", item_code="A", **values)

    def test_copies_headers_and_matches_duplicate_item_rows_by_reference(self):
        doc = Delivery(items=[self.row("R1"), self.row("R2")])
        self.api.fill_delivery_note(doc)
        self.assertEqual(doc.custom_project_title, "Project")
        self.assertEqual(doc.custom_technical_team, "Team")
        self.assertEqual([row.custom_note for row in doc.items], ["First", "Second"])

    def test_preserves_edits_and_explicitly_cleared_notes(self):
        doc = Delivery(custom_project_title="Edited", items=[
            self.row("R1", custom_note="Edited"),
            self.row("R2", custom_note="", custom_note_initialized=1)])
        self.api.fill_delivery_note(doc)
        self.api.fill_delivery_note(doc)
        self.assertEqual(doc.custom_project_title, "Edited")
        self.assertEqual([row.custom_note for row in doc.items], ["Edited", ""])

    def test_conflicting_orders_leave_headers_empty(self):
        doc = Delivery(items=[self.row("R1"), Doc(against_sales_order="SO2")])
        self.api.fill_delivery_note(doc)
        self.assertFalse(doc.get("custom_project_title"))
        self.assertFalse(doc.get("custom_technical_team"))

    def test_mismatched_source_row_does_not_copy_note(self):
        row = self.row("R1")
        row.item_code = "B"
        self.api.fill_delivery_note(Delivery(items=[row]))
        self.assertFalse(row.get("custom_note_initialized"))
        self.assertFalse(row.get("custom_note"))

    def test_project_action_fetches_business_number_instead_of_project_id(self):
        doc = Delivery(project="PROJ-0001", items=[self.row("R1")])
        self.api.fill_delivery_note(doc)
        self.assertEqual(doc.custom_project_no, "P-8716")

    def test_project_number_follows_changed_project(self):
        doc = Delivery(project="PROJ-0001", custom_project_no="Old", items=[])
        self.api.fill_delivery_note(doc)
        doc.project = "PROJ-0002"
        self.api.fill_delivery_note(doc)
        self.assertEqual(doc.custom_project_no, "P-2000")

    def test_fetches_single_item_project_but_does_not_choose_between_projects(self):
        doc = Delivery(items=[self.row("R1", project="PROJ-0001")])
        self.api.fill_delivery_note(doc)
        self.assertEqual(doc.custom_project_no, "P-8716")
        doc.items.append(self.row("R2", project="PROJ-0002"))
        self.api.fill_delivery_note(doc)
        self.assertEqual(doc.custom_project_no, "")

    def test_removed_project_clears_old_number(self):
        doc = Delivery(custom_project_no="Old", items=[])
        self.api.fill_delivery_note(doc)
        self.assertEqual(doc.custom_project_no, "")
