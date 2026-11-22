import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module
from test_project_boq import Doc


class TestQuotationProjectDetails(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe.get_meta = Mock(side_effect=lambda dt: Doc(fields=[
            Doc(fieldname="custom_project_title", label="Project Title") if dt == "Quotation"
            else Doc(fieldname="custom_note", label="Note")]))
        self.sources = {
            "Q1-R1": Doc(parent="Q1", item_code="A", custom_note="First"),
            "Q1-R2": Doc(parent="Q1", item_code="A", custom_note="Second"),
        }
        self.frappe.db = Mock()
        self.frappe.db.get_value.side_effect = lambda dt, name, *a, **kw: (
            self.sources.get(name) if dt == "Quotation Item" else {"Q1": "Project One", "Q2": "Project Two"}.get(name))
        modules = patch.dict(sys.modules, {"frappe": self.frappe})
        modules.start()
        self.addCleanup(modules.stop)
        self.api = load_module("c4factory/api/quotation_project_details.py", "quotation_project_details_test")

    def row(self, source, **values):
        return Doc(item_code="A", quotation_item=source, prevdoc_docname="Q1", **values)

    def test_repeated_items_copy_their_own_source_notes_and_title(self):
        order = Doc(items=[self.row("Q1-R1"), self.row("Q1-R2")])
        self.api.fill_sales_order(order)
        self.assertEqual([r.custom_note for r in order.items], ["First", "Second"])
        self.assertEqual(order.custom_project_title, "Project One")

    def test_user_edits_and_explicit_empty_note_survive_validation(self):
        order = Doc(custom_project_title="Edited", items=[
            self.row("Q1-R1", custom_note="Edited", custom_note_initialized=1),
            self.row("Q1-R2", custom_note="", custom_note_initialized=1)])
        self.api.fill_sales_order(order)
        self.assertEqual([r.custom_note for r in order.items], ["Edited", ""])
        self.assertEqual(order.custom_project_title, "Edited")

    def test_invalid_source_row_is_not_copied(self):
        row = self.row("Q1-R1")
        row.item_code = "B"
        order = Doc(items=[row])
        self.api.fill_sales_order(order)
        self.assertIsNone(row.get("custom_note"))
        self.assertFalse(row.get("custom_note_initialized"))

    def test_existing_note_is_preserved_during_backfill(self):
        order = Doc(items=[self.row("Q1-R1", custom_note="Existing")])
        self.api.fill_sales_order(order)
        self.assertEqual(order.items[0].custom_note, "Existing")
        self.assertEqual(order.items[0].custom_note_initialized, 1)

    def test_conflicting_quotation_titles_are_not_chosen_arbitrarily(self):
        order = Doc(items=[self.row("Q1-R1"), Doc(item_code="A", prevdoc_docname="Q2")])
        self.api.fill_sales_order(order)
        self.assertFalse(order.get("custom_project_title"))
