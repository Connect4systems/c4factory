import unittest
from unittest.mock import Mock, patch

from c4factory.api import sales_order_project as api


class Doc(dict):
	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__

	def db_set(self, values, **kwargs):
		self.update(values)


class TestSalesOrderProject(unittest.TestCase):
	def setUp(self):
		self.doc = Doc(name="SO-1", docstatus=1, customer="CUST", customer_name="Customer",
			company="Company", custom_project_no=" P-1 ", custom_technical_team="Team",
			transaction_date="2026-11-20", delivery_date="2026-12-20")
		self.project = Mock()
		self.project.name = "P-1"
		self.project.is_new.return_value = True
		self.patches = [
			patch.object(api.frappe, "get_meta", return_value=Mock(fields=[])),
			patch.object(api.frappe.db, "sql", return_value=[]),
			patch.object(api.frappe.db, "exists", return_value=None),
			patch.object(api.frappe, "new_doc", return_value=self.project),
		]
		for item in self.patches:
			item.start()
			self.addCleanup(item.stop)

	def test_creation_maps_identity_dates_team_and_order(self):
		api.on_submit(self.doc)
		self.project.insert.assert_called_once_with(ignore_permissions=True, set_name="P-1")
		self.assertEqual(self.project.project_name, "P-1 \u2013 Customer")
		self.assertEqual(self.project.custom_technical_team, "Team")
		self.assertEqual(self.project.expected_start_date, "2026-11-20")
		self.assertEqual(self.project.expected_end_date, "2026-12-20")
		self.assertEqual(self.project.sales_order, "SO-1")
		self.assertEqual(self.doc.project, "P-1")
		self.assertEqual(self.doc.custom_project_no, "P-1")

	def test_blank_number_blocks_submission(self):
		self.doc.custom_project_no = " "
		with patch.object(api.frappe, "throw", side_effect=ValueError), self.assertRaises(ValueError):
			api.on_submit(self.doc)

	def test_draft_does_not_create_project(self):
		self.doc.docstatus = 0
		api.on_submit(self.doc)
		self.project.insert.assert_not_called()

	def existing(self, **values):
		project = Mock()
		project.name = "P-1"
		project.customer = "CUST"
		project.company = "Company"
		project.project_name = "P-1"
		project.get.side_effect = {"sales_order": "SO-1", "custom_project_no": "P-1", **values}.get
		project.is_new.return_value = False
		return project

	def test_retry_reuses_project(self):
		project = self.existing()
		self.doc.project = "P-1"
		with patch.object(api.frappe.db, "exists", return_value="P-1"), patch.object(api.frappe, "get_doc", return_value=project):
			api.on_submit(self.doc)
		project.insert.assert_not_called()
		project.save.assert_called_once_with(ignore_permissions=True)

	def test_collision_rejected(self):
		project = self.existing(sales_order="OTHER")
		with patch.object(api.frappe.db, "exists", return_value="P-1"), patch.object(api.frappe, "get_doc", return_value=project), patch.object(api.frappe, "throw", side_effect=ValueError), self.assertRaises(ValueError):
			api.on_submit(self.doc)

	def test_amendment_reuses_existing_project(self):
		self.doc.amended_from = "OLD-SO"
		project = self.existing(sales_order="OLD-SO")
		with patch.object(api.frappe.db, "exists", return_value="P-1"), patch.object(api.frappe, "get_doc", return_value=project):
			api.on_submit(self.doc)
		self.assertEqual(project.sales_order, "SO-1")
		project.save.assert_called_once()
