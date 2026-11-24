"""Sales Order details reach Projects through submission and manual creation."""
import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from test_part_list_save import load_module
import test_project_boq
from test_project_boq import Doc


class TestProjectSalesDetails(unittest.TestCase):
	setUp = test_project_boq.TestProjectBOQ.setUp
	def test_manual_project_fetches_title_and_partner_from_selected_order(self):
		project = Doc(sales_order="SO-1", custom_project_title="Old", custom_sales_partner="Old Partner")
		self.frappe.db.get_value.side_effect = lambda dt, name, field: {
			"customer": "Customer", "custom_project_title": "New Title", "sales_partner": "Partner",
		}[field]
		with patch.object(self.api, "build_rows", return_value=[]), patch.object(self.api, "resolve_sales_order", return_value="SO-1"):
			project.set = Mock()
			self.api.validate_project(project)
		self.assertEqual(project.custom_project_title, "New Title")
		self.assertEqual(project.custom_sales_partner, "Partner")

	def test_project_without_order_keeps_its_details(self):
		project = Doc(custom_project_title="Independent", custom_sales_partner="Partner")
		with patch.object(self.api, "resolve_sales_order", return_value=None):
			self.api.validate_project(project)
		self.assertEqual(project.custom_project_title, "Independent")
		self.assertEqual(project.custom_sales_partner, "Partner")


class TestSubmissionDetails(unittest.TestCase):
	def test_submission_copies_title_and_sales_partner(self):
		frappe = ModuleType("frappe")
		frappe._ = lambda value: value
		frappe.db = Mock()
		frappe.db.exists.return_value = None
		frappe.get_meta = Mock(return_value=Doc(fields=[]))
		project = Mock()
		project.name = "P-1"
		frappe.new_doc = Mock(return_value=project)
		order = Doc(name="SO-1", docstatus=1, custom_project_no="P-1", customer="Customer",
			company="Company", custom_project_title="Office Fitout", sales_partner="Partner", db_set=Mock())
		with patch.dict(sys.modules, {"frappe": frappe}):
			api = load_module("c4factory/api/sales_order_project.py", "sales_order_project_details_test")
			api.on_submit(order)
		self.assertEqual(project.custom_project_title, "Office Fitout")
		self.assertEqual(project.custom_sales_partner, "Partner")
		project.insert.assert_called_once_with(ignore_permissions=True, set_name="P-1")
