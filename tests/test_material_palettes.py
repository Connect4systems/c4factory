"""Palette integrity checks runnable without a bench."""
import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch
from test_part_list_save import load_module


class TestMaterialPalettes(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType('frappe')
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


if __name__ == '__main__':
    unittest.main()
