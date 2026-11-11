"""Spreadsheet parsing and accessory authorization checks without a Frappe bench."""
import copy
import io
import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from test_part_list_save import ROOT, load_module


class Doc(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def set(self, key, value):
        self[key] = value

    def get_doc_before_save(self):
        return self.get("previous")


def row(doctype, **values):
    folder = doctype.lower().replace(' ', '_')
    schema = json.loads((ROOT / f'c4factory/c4factory/doctype/{folder}/{folder}.json').read_text())
    return Doc(meta=SimpleNamespace(fields=[SimpleNamespace(**f) for f in schema['fields']]), **values)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType('frappe')
        self.frappe._ = lambda text: text
        self.frappe.whitelist = lambda: lambda fn: fn
        self.frappe.throw = Mock(side_effect=ValueError)
        self.frappe.PermissionError = PermissionError
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.get_roles = Mock(return_value=['Stock User'])
        self.frappe.session = SimpleNamespace(user='stock@example.com')
        self.frappe.db = Mock()
        self.frappe.db.exists.return_value = False
        self.frappe.db.get_value.return_value = 0
        self.frappe.get_doc = Mock()
        utils = ModuleType('frappe.utils')
        utils.now_datetime = lambda: 'NOW'
        self.modules = patch.dict(sys.modules, {'frappe': self.frappe, 'frappe.utils': utils})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.api = load_module('c4factory/api/part_list_import.py', 'import_test')
        self.stock = load_module('c4factory/api/part_list_accessories.py', 'stock_test')

    def accessory(self, **values):
        data = dict(name='ACC-1', idx=1, requested_name='Screw', qty=4, item=None)
        data.update(values)
        return row('Accessorise Table', **data)

    def document(self, accessories):
        return Doc(name='PL-1', modified='STAMP', docstatus=1, accessorise_table=accessories,
            check_permission=Mock())

    def item(self):
        return Doc(name='SCREW', stock_uom='Nos', description='Stock screw', disabled=0,
            is_stock_item=1, has_variants=0, uoms=[Doc(uom='Box', conversion_factor=10)], check_permission=Mock())

    def test_multiline_paste_and_blank_dimensions_preserve_columns(self):
        matrix = self.api.parse_paste('Top\tقرصة\t1200\t\t25\t3\r\n')
        result = self.api.build_preview(matrix, dict(part_name=0, part_name_ar=1, lenght=2, hight=3, thickness=4, qty=5), 'panel_materials', 'MDF')
        self.assertEqual(result[0]['errors'], [])
        self.assertIsNone(result[0]['values']['hight'])
        self.assertEqual(result[0]['values']['thickness'], 25)
        pasted = self.api.parse_paste('"Screw\nlong"\t8\n')
        self.assertEqual(pasted, [['Screw\nlong', '8']])

    def test_all_template_has_four_sections_and_their_columns(self):
        self.frappe.response = {}
        self.api.download_template('all')
        workbook = self.api.read_workbook(self.frappe.response['filecontent'], 'all.xlsx')
        rows = workbook['Import']
        titles = ['Panel Materials', 'Metal Material', 'Other Material', 'Accessories']
        self.assertEqual([rows[index][0] for index in (0, 3, 6, 9)], titles)
        self.assertEqual(rows[1][0], 'Part Name English')
        self.assertEqual(rows[10], rows[1], 'All sections use the same column layout')

    def test_invalid_numbers_and_missing_arabic_are_preview_errors(self):
        for qty in ('0', '-1', 'nan', 'inf', 'abc'):
            preview = self.api.build_preview([['Top', '', qty]], {'part_name': 0, 'part_name_ar': 1, 'qty': 2}, 'metal_material', 'Steel')
            self.assertGreaterEqual(len(preview[0]['errors']), 2)

    def test_duplicate_columns_and_wrong_table_fields_rejected(self):
        for mapping in ({'requested_name': 0, 'qty': 0}, {'requested_name': 0, 'qty': 1, 'part_name': 2}):
            with self.assertRaises(ValueError):
                self.api.build_preview([['Screw', 2, 'x']], mapping, 'accessorise_table')

    def test_row_ranges_skip_headers_and_keep_actual_source_number(self):
        preview = self.api.build_preview([['Name', 'Qty'], ['Screw', 8], ['', ''], ['Nut', 4]],
            {'requested_name': 0, 'qty': 1}, 'accessorise_table', start_row=2, end_row=3)
        self.assertEqual([r['source_row'] for r in preview], [2])

    def test_xlsx_reader_does_not_evaluate_formulas(self):
        from openpyxl import Workbook
        book = Workbook(); book.active.append(['Screw', '=1+1'])
        content = io.BytesIO(); book.save(content)
        self.assertEqual(self.api.read_workbook(content.getvalue(), 'test.xlsx')['Sheet'], [['Screw', '']])

    def test_file_permission_and_import_permission_are_checked(self):
        self.frappe.has_permission.return_value = False
        with self.assertRaises(ValueError):
            self.api.inspect_workbook('/private/files/no.xls')
        self.frappe.get_doc.assert_not_called()
        self.frappe.has_permission.return_value = True
        self.frappe.get_doc.return_value.check_permission.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.api.inspect_workbook('/private/files/no.xls')

    def test_pending_accessories_can_be_saved_but_block_production(self):
        doc = self.document([self.accessory(mapping_status='Matched', mapped_by='spoof')])
        self.stock.validate_requirements(doc)
        self.assertEqual(doc.accessorise_table[0].mapping_status, 'Pending')
        self.assertIsNone(doc.accessorise_table[0].mapped_by)
        with self.assertRaises(ValueError):
            self.stock.require_mapped(doc)

    def test_mapping_validates_item_uom_and_records_stock_quantity(self):
        self.frappe.get_doc.return_value = self.item()
        doc = self.document([self.accessory(item='SCREW', requested_uom='Box', conversion_factor=10)])
        self.stock.validate_requirements(doc)
        row = doc.accessorise_table[0]
        self.assertEqual((row.stock_qty, row.stock_uom, row.mapping_status), (40, 'Nos', 'Matched'))
        self.assertEqual(row.requested_name, 'Screw')
        self.assertEqual((row.mapped_by, row.mapped_on), ('stock@example.com', 'NOW'))
        self.frappe.get_doc.return_value.check_permission.assert_called_once_with('read')

    def test_conversion_and_disabled_or_nonstock_items_rejected(self):
        for changes in ({'conversion_factor': 0}, {'conversion_factor': -1}, {'conversion_factor': float('inf')},
                        {'requested_uom': 'Box', 'conversion_factor': 2}):
            self.frappe.get_doc.return_value = self.item()
            with self.assertRaises(ValueError):
                self.stock.validate_requirements(self.document([self.accessory(item='SCREW', **changes)]))
        for changes in ({'disabled': 1}, {'is_stock_item': 0}, {'has_variants': 1}):
            item = self.item(); item.update(changes); self.frappe.get_doc.return_value = item
            with self.assertRaises(ValueError):
                self.stock.validate_requirements(self.document([self.accessory(item='SCREW')]))

    def test_whole_number_stock_uom(self):
        self.frappe.get_doc.return_value = self.item()
        self.frappe.db.get_value.return_value = 1
        with self.assertRaises(ValueError):
            self.stock.validate_requirements(self.document([self.accessory(item='SCREW', qty=0.5)]))

    def test_new_parts_require_bilingual_names_but_existing_rows_survive(self):
        doc = self.document([])
        doc.panel_materials = [row('Part List Materials', name='OLD', idx=1, part_name='Top', qty=1)]
        with self.assertRaises(ValueError):
            self.stock.validate_requirements(doc)
        doc.previous = self.document([])
        doc.previous.panel_materials = copy.deepcopy(doc.panel_materials)
        self.stock.validate_requirements(doc)

    def submitted_pair(self):
        old = self.document([self.accessory()])
        doc = copy.deepcopy(old)
        doc.previous = old
        doc.accessorise_table[0].item = 'SCREW'
        self.frappe.get_doc.return_value = self.item()
        return doc

    def test_stock_roles_can_only_map_not_change_submitted_requirements(self):
        doc = self.submitted_pair()
        self.stock.validate_submitted_update(doc)
        for field, value in [('qty', 10), ('requested_name', 'Different'), ('note', 'changed')]:
            doc = self.submitted_pair(); doc.accessorise_table[0][field] = value
            with self.assertRaises(ValueError):
                self.stock.validate_submitted_update(doc)
        doc = self.submitted_pair(); doc.width = 500
        with self.assertRaises(ValueError):
            self.stock.validate_submitted_update(doc)

    def test_stock_role_and_production_use_guards(self):
        self.frappe.get_roles.return_value = ['Technical']
        with self.assertRaises(ValueError):
            self.stock.validate_submitted_update(self.submitted_pair())
        self.frappe.get_roles.return_value = ['Stock Manager']
        self.frappe.db.exists.return_value = True
        with self.assertRaises(ValueError):
            self.stock.validate_submitted_update(self.submitted_pair())

    def test_audit_fields_cannot_be_spoofed(self):
        doc = self.submitted_pair()
        self.stock.validate_submitted_update(doc)
        old = copy.deepcopy(doc); old.pop('previous')
        doc.previous = old
        doc.accessorise_table[0].mapped_by = 'attacker'
        doc.accessorise_table[0].mapped_on = 'yesterday'
        self.stock.validate_submitted_update(doc)
        self.assertEqual(doc.accessorise_table[0].mapped_by, 'stock@example.com')
        self.assertEqual(doc.accessorise_table[0].mapped_on, 'NOW')

    def test_mapping_api_rejects_stale_and_duplicate_rows(self):
        doc = self.document([self.accessory()]); self.frappe.get_doc.return_value = doc
        with self.assertRaises(ValueError):
            self.stock.map_accessories('PL-1', [], 'STALE')
        mappings = [{'row': 'ACC-1', 'item': 'SCREW'}, {'row': 'ACC-1', 'item': 'SCREW'}]
        with self.assertRaises(ValueError):
            self.stock.map_accessories('PL-1', mappings, 'STAMP')
        doc.check_permission.assert_called_with('read')

    def test_mapping_api_saves_only_whitelisted_fields_via_guarded_controller(self):
        doc = self.submitted_pair()
        item = self.item()
        self.frappe.get_doc.side_effect = lambda doctype, name: doc if doctype == 'Part List' else item
        doc.save = Mock(side_effect=lambda **kwargs: self.stock.validate_submitted_update(doc))
        result = self.stock.map_accessories('PL-1', [{'row':'ACC-1', 'item':'SCREW',
            'requested_uom':'Box', 'conversion_factor':10, 'qty':999, 'requested_name':'spoof'}], 'STAMP')
        doc.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(result, {'matched':1, 'total':1})
        self.assertEqual(doc.accessorise_table[0].qty, 4)
        self.assertEqual(doc.accessorise_table[0].requested_name, 'Screw')
        self.assertEqual(doc.accessorise_table[0].stock_qty, 40)


if __name__ == '__main__':
    unittest.main()
