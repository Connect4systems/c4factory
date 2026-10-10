import unittest
from unittest.mock import Mock, patch

from c4factory.api import sales_order_project as api


class Doc(dict):
	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__


class TestSalesOrderProject(unittest.TestCase):
	def setUp(self):
		self.doc = Doc(name="SO-1", customer="Customer", company="Company", custom_project_no=" P-1 ")
		self.project = Mock(name="project")
		self.project.name = "PROJ-0001"

	def test_blank_number_blocks_submit(self):
		self.doc.custom_project_no = "  "
		with patch.object(api.frappe, "throw", side_effect=ValueError), self.assertRaises(ValueError):
			api.before_submit(self.doc)

	def test_creation_sets_name_customer_order_and_link(self):
		with patch.object(api.frappe.db, "exists", return_value=False), patch.object(
			api.frappe, "get_doc", return_value=self.project
		) as get_doc:
			api.before_submit(self.doc)
		self.assertEqual(self.doc.project, "PROJ-0001")
		self.assertEqual(self.doc.custom_project_no, "P-1")
		values = get_doc.call_args.args[0]
		self.assertEqual(values["project_name"], "P-1")
		self.assertEqual(values["customer"], "Customer")
		self.assertEqual(values["sales_order"], "SO-1")
		self.project.insert.assert_called_once_with(ignore_permissions=True)

	def test_duplicate_number_blocks_submit(self):
		with patch.object(api.frappe.db, "exists", return_value=True), patch.object(
			api.frappe, "throw", side_effect=ValueError
		), self.assertRaises(ValueError):
			api.before_submit(self.doc)

	def test_unrelated_project_blocks_submit(self):
		self.doc.project = "PROJ-0001"
		project = Doc(project_name="P-1", customer="Customer", company="Company", sales_order="SO-2")
		with patch.object(api.frappe, "get_doc", return_value=project), patch.object(
			api.frappe, "throw", side_effect=ValueError
		), self.assertRaises(ValueError):
			api.before_submit(self.doc)
