"""Project BOQ setup supports sites with an existing numeric Project No."""

import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module


class TestProjectBOQMigration(unittest.TestCase):
	def run_migration(self, existing_type):
		frappe = ModuleType("frappe")
		frappe.db = Mock()
		frappe.db.get_value.return_value = existing_type
		custom_field = ModuleType("frappe.custom.doctype.custom_field.custom_field")
		custom_field.create_custom_fields = Mock()
		with patch.dict(sys.modules, {"frappe": frappe, custom_field.__name__: custom_field}):
			module = load_module("c4factory/patches/v1_0/setup_project_boq.py", "project_boq_migration_test")
			module.execute()
		return frappe, custom_field.create_custom_fields

	def test_existing_float_converts_only_project_number_before_normal_setup(self):
		frappe, create_fields = self.run_migration("Float")
		self.assertEqual(create_fields.call_count, 2)
		conversion, setup = create_fields.call_args_list
		self.assertEqual(set(conversion.args[0]), {"Project"})
		self.assertEqual(len(conversion.args[0]["Project"]), 1)
		self.assertEqual(conversion.args[0]["Project"][0]["fieldname"], "custom_project_no")
		self.assertEqual(conversion.args[0]["Project"][0]["fieldtype"], "Data")
		self.assertEqual(conversion.kwargs, {"ignore_validate": True, "update": True})
		self.assertEqual(setup.kwargs, {"update": True})
		frappe.db.sql.assert_not_called()
		frappe.db.set_value.assert_not_called()

	def test_new_sites_and_repeat_runs_use_normal_validation(self):
		for existing_type in (None, "Data"):
			with self.subTest(existing_type=existing_type):
				_, create_fields = self.run_migration(existing_type)
				create_fields.assert_called_once()
				self.assertEqual(create_fields.call_args.kwargs, {"update": True})

	def test_other_types_do_not_bypass_validation(self):
		_, create_fields = self.run_migration("Link")
		create_fields.assert_called_once()
		self.assertNotIn("ignore_validate", create_fields.call_args.kwargs)
