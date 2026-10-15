"""Palette integrity checks runnable without a bench."""
import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch
from test_part_list_save import load_module


class TestMaterialPalettes(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType('frappe')
        self.frappe.whitelist = lambda: lambda fn: fn
        self.frappe.validate_and_sanitize_search_inputs = lambda fn: fn
        self.frappe._ = lambda message: message
        self.frappe.db = Mock()
        self.frappe.throw = Mock(side_effect=ValueError)
        self.modules = patch.dict(sys.modules, {'frappe': self.frappe})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.api = load_module('c4factory/api/part_list_material_colors.py', 'palette_validation')

    def test_accepts_color_in_selected_palette(self):
        self.frappe.db.exists.return_value = True
        self.api.validate_palette_color('Wood', 'Oak')
        self.frappe.db.exists.assert_called_once_with('Material Color', {'name': 'Oak', 'palette': 'Wood'})

    def test_rejects_color_outside_palette(self):
        self.frappe.db.exists.return_value = False
        with self.assertRaises(ValueError):
            self.api.validate_palette_color('Metal', 'Oak')

    def test_rejects_color_without_palette(self):
        with self.assertRaises(ValueError):
            self.api.validate_palette_color(None, 'Oak')

    def test_empty_color_allowed(self):
        self.api.validate_palette_color('Wood', None)
        self.frappe.db.exists.assert_not_called()


    def test_search_uses_material_palette_when_row_palette_is_missing(self):
        self.frappe.db.get_value.return_value = 'HPL'
        self.frappe.get_list = Mock(return_value=[['White', 'White']])
        result = self.api.material_color_query('P-Wood', '', 'name', 0, 20, {'material': 'HPL'})
        self.assertEqual(result, [['White', 'White']])
        self.frappe.db.get_value.assert_called_once_with('Part Material', 'HPL', 'color_palette')
        self.assertEqual(self.frappe.get_list.call_args.args, ('Material Color',))
        self.assertEqual(self.frappe.get_list.call_args.kwargs['filters'], {'palette': 'HPL'})
        self.assertEqual(self.frappe.get_list.call_args.kwargs['fields'], ['name'])
        self.assertEqual(set(self.frappe.get_list.call_args.kwargs['or_filters']), {'name'})

    def test_search_without_palette_returns_no_colors(self):
        self.frappe.get_list = Mock()
        self.assertEqual(self.api.material_color_query('Material Color', '', 'name', 0, 20, {}), [])
        self.frappe.get_list.assert_not_called()

    def test_explicit_row_palette_takes_precedence(self):
        self.frappe.get_list = Mock(return_value=[])
        self.api.material_color_query('Material Color', 'White', 'name', 0, 20,
                                      {'palette': 'HPL', 'material': 'Panel'})
        self.frappe.db.get_value.assert_not_called()
        self.assertEqual(self.frappe.get_list.call_args.kwargs['filters'], {'palette': 'HPL'})
        self.assertEqual(self.frappe.get_list.call_args.kwargs['fields'], ['name'])
        self.assertEqual(set(self.frappe.get_list.call_args.kwargs['or_filters']), {'name'})

    def test_retired_migration_never_imports_legacy_records(self):
        migration = load_module('c4factory/patches/v1_0/migrate_material_color_palettes.py', 'retired_colors')
        self.frappe.get_all = Mock()
        self.frappe.get_doc = Mock()
        migration.execute()
        self.frappe.get_all.assert_not_called()
        self.frappe.get_doc.assert_not_called()


    def part_material(self, **values):
        document = ModuleType('frappe.model.document')
        document.Document = type('Document', (), {'get': lambda doc, key: getattr(doc, key, None)})
        with patch.dict(sys.modules, {
            'frappe.model': ModuleType('frappe.model'),
            'frappe.model.document': document,
            'c4factory.api.part_list_material_colors': self.api,
        }):
            controller = load_module('c4factory/c4factory/doctype/part_material/part_material.py', 'part_material_optional_color')
        doc = controller.PartMaterial()
        for key, value in values.items():
            setattr(doc, key, value)
        return doc

    def test_part_material_saves_with_palette_and_no_color_attribute(self):
        doc = self.part_material(material='HPL', color_palette='HPL')
        self.assertFalse(hasattr(doc, 'color'))
        doc.validate()
        self.frappe.db.exists.assert_not_called()

    def test_part_material_still_rejects_default_color_in_another_palette(self):
        self.frappe.db.exists.return_value = False
        doc = self.part_material(material='HPL', color_palette='HPL', color='Oak')
        with self.assertRaises(ValueError):
            doc.validate()

    def test_part_material_accepts_default_color_in_its_palette(self):
        self.frappe.db.exists.return_value = True
        self.part_material(material='HPL', color_palette='HPL', color='White').validate()
        self.frappe.db.exists.assert_called_once_with('Material Color', {'name': 'White', 'palette': 'HPL'})


if __name__ == '__main__':
    unittest.main()
