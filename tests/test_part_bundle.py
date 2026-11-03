"""Bundle payload checks runnable without a Frappe bench."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class TestPartBundle(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe.whitelist = lambda: lambda fn: fn
        self.frappe._ = lambda text: text
        self.frappe.throw = Mock(side_effect=ValueError("Invalid quantity"))
        self.frappe.get_doc = Mock()

        def meta(child_type):
            folder = child_type.lower().replace(" ", "_")
            data = json.loads((ROOT / f"c4factory/c4factory/doctype/{folder}/{folder}.json").read_text())
            fields = [SimpleNamespace(**field) for field in data["fields"]]
            return SimpleNamespace(fields=fields, get_valid_columns=lambda: [f.fieldname for f in fields])

        self.frappe.get_meta = meta
        with patch.dict(sys.modules, {"frappe": self.frappe}):
            spec = importlib.util.spec_from_file_location("bundle_test", ROOT / "c4factory/api/part_bundle.py")
            self.api = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.api)

    def test_four_tables_scale_and_preserve_details_without_identities(self):
        rows = {table: [{"name": "old-row", "parent": "bundle", "qty": 3,
                         "material": "MDF", "basic_color": "Oak", "width": 100,
                         "item": "HINGE", "description": "Hinge"}]
                for table in self.api.BUNDLE_TABLES}
        original = json.dumps(rows)
        bundle = Mock()
        bundle.get.side_effect = rows.get
        self.frappe.get_doc.return_value = bundle
        result = self.api.get_bundle_rows("Example", 4)
        bundle.check_permission.assert_called_once_with("read")
        self.assertEqual(set(result), set(rows))
        for table in rows:
            self.assertEqual(result[table][0]["qty"], 12)
            self.assertNotIn("name", result[table][0])
            self.assertNotIn("parent", result[table][0])
        self.assertEqual(result["panel_materials"][0]["basic_color"], "Oak")
        self.assertEqual(result["panel_materials"][0]["width"], 100)
        self.assertEqual(result["accessorise_table"][0]["description"], "Hinge")
        self.assertEqual(json.dumps(rows), original)

    def test_invalid_multiplier_rejected_before_loading_bundle(self):
        for qty in (0, -1, "invalid", "nan", "inf", None):
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                self.api.get_bundle_rows("Example", qty)
        self.frappe.get_doc.assert_not_called()

    def test_bundle_read_permission_is_required(self):
        self.frappe.get_doc.return_value.check_permission.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.api.get_bundle_rows("Private bundle", 1)


if __name__ == "__main__":
    unittest.main()
