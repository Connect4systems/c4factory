"""Workbook migration preserves legacy URLs without duplicating PDS rows."""
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from test_part_list_save import load_module


class TestPartFileMigration(unittest.TestCase):
    def run_migration(self, existing):
        frappe = ModuleType('frappe')
        frappe.db = Mock()
        frappe.clear_cache = Mock()
        frappe.get_doc = Mock()
        frappe.db.has_column.return_value = True
        frappe.db.exists.return_value = existing
        frappe.db.sql.return_value = [(2,)]
        frappe.get_all = Mock(side_effect=[['title-label'], [SimpleNamespace(
            name='PL-1', part_file='/private/files/parts.xls', docstatus=1,
        )], ['FILE-1']])
        with patch.dict(sys.modules, {'frappe': frappe}):
            module = load_module('c4factory/patches/v1_0/move_part_file_to_pds_table.py', 'part_file_migration')
            module.execute()
        frappe.db.set_value.assert_any_call('Property Setter', 'title-label', 'value', 'Title')
        frappe.db.set_value.assert_any_call('Part List', 'PL-1', 'part_file', None, update_modified=False)
        frappe.db.set_value.assert_any_call('File', 'FILE-1', 'attached_to_field', 'pds_table', update_modified=False)
        return frappe

    def test_moves_file_and_preserves_parent_status(self):
        frappe = self.run_migration(False)
        row = frappe.get_doc.call_args.args[0]
        self.assertEqual(row['title'], 'Part File')
        self.assertEqual(row['arttach'], '/private/files/parts.xls')
        self.assertEqual(row['idx'], 3)
        self.assertEqual(row['docstatus'], 1)
        self.assertEqual(row['parentfield'], 'pds_table')
        frappe.get_doc.return_value.db_insert.assert_called_once()

    def test_existing_attachment_is_not_duplicated(self):
        frappe = self.run_migration(True)
        frappe.get_doc.assert_not_called()
