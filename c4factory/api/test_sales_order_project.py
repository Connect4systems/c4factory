import unittest
from unittest.mock import Mock, patch

from c4factory.api import sales_order_project as api


class Doc(dict):
	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__

	def db_set(self, field, value=None, **kwargs):
		self.setdefault("db_updates", []).append((field, value, kwargs))
		self.update(field if isinstance(field, dict) else {field: value})


class TestSalesOrderProject(unittest.TestCase):
	def setUp(self):
		self.doc = Doc(name="SO-1", docstatus=1, customer="Customer", company="Company", custom_project_no=" P-1 ")
		self.project = Mock(name="project")
		self.project.name = "PROJ-0001"
		meta_patch = patch.object(api.frappe, "get_meta", return_value=Mock(fields=[]))
		self.project_meta = meta_patch.start().return_value
		self.addCleanup(meta_patch.stop)

	def test_blank_number_blocks_submit(self):
		self.doc.custom_project_no = "  "
		with patch.object(api.frappe, "throw", side_effect=ValueError), self.assertRaises(ValueError):
			api.on_submit(self.doc)

	def test_creation_sets_name_customer_order_and_link(self):
		with patch.object(api.frappe.db, "exists", return_value=False), patch.object(
			api.frappe, "get_doc", return_value=self.project
		) as get_doc:
			api.on_submit(self.doc)
		self.assertEqual(self.doc.project, "PROJ-0001")
		self.assertEqual(self.doc.custom_project_no, "P-1")
		values = get_doc.call_args.args[0]
		self.assertEqual(values["project_name"], "P-1")
		self.assertEqual(values["customer"], "Customer")
		self.assertEqual(values["sales_order"], "SO-1")
		self.project.insert.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(self.doc.db_updates, [
			({"project": "PROJ-0001", "custom_project_no": "P-1"}, None, {"update_modified": False})
		])

	def test_duplicate_number_blocks_submit(self):
		project = Doc(project_name="P-1", customer="Other Customer", company="Company", sales_order="SO-2")
		with patch.object(api.frappe, "get_doc", return_value=project), patch.object(api.frappe.db, "exists", return_value="OTHER"), patch.object(
			api.frappe, "throw", side_effect=ValueError
		), self.assertRaises(ValueError):
			api.on_submit(self.doc)

	def test_unrelated_project_blocks_submit(self):
		self.doc.project = "PROJ-0001"
		project = Doc(project_name="P-1", customer="Customer", company="Company", sales_order="SO-2")
		with patch.object(api.frappe.db, "exists", return_value="PROJ-0001"), patch.object(api.frappe, "get_doc", return_value=project), patch.object(
			api.frappe, "throw", side_effect=ValueError
		), self.assertRaises(ValueError):
			api.on_submit(self.doc)

	def test_workflow_request_does_not_create_or_validate_project(self):
		self.doc.docstatus = 0
		self.doc.workflow_state = "Pending"
		self.doc.custom_project_no = ""
		self.doc.project = "UNRELATED-PROJECT"
		with patch.object(api.frappe, "get_doc") as get_doc, patch.object(
			api.frappe, "throw"
		) as throw:
			api.on_submit(self.doc)
		get_doc.assert_not_called()
		throw.assert_not_called()
		self.assertNotIn("db_updates", self.doc)

	def test_matching_project_is_reused_and_linked(self):
		self.doc.project = self.project.name
		self.project.project_name = "P-1"
		self.project.get.side_effect = {"customer": "Customer", "company": "Company", "sales_order": "SO-1"}.get
		with patch.object(api.frappe, "get_doc", return_value=self.project):
			api.on_submit(self.doc)
		self.project.insert.assert_not_called()
		self.project.save.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(self.doc.custom_project_no, "P-1")

	def test_stale_link_is_replaced_with_new_project(self):
		self.doc.project = "OLD-PROJECT"
		old = Doc(project_name="OLD", customer="Customer", company="Company", sales_order="SO-OLD")
		with patch.object(api.frappe.db, "exists", return_value=False), patch.object(
			api.frappe, "get_doc", side_effect=[old, self.project]
		):
			api.on_submit(self.doc)
		self.assertEqual(self.doc.project, "PROJ-0001")
		self.assertEqual(old.sales_order, "SO-OLD")
		self.project.insert.assert_called_once_with(ignore_permissions=True)

	def test_matching_unassigned_project_is_reused(self):
		self.project.project_name = "P-1"
		self.project.get.side_effect = {"customer": "Customer", "company": "Company", "sales_order": None}.get
		with patch.object(api.frappe.db, "exists", return_value=self.project.name), patch.object(
			api.frappe, "get_doc", return_value=self.project
		):
			api.on_submit(self.doc)
		self.assertEqual(self.doc.project, self.project.name)
		self.assertEqual(self.project.sales_order, "SO-1")
		self.project.insert.assert_not_called()
		self.project.save.assert_called_once_with(ignore_permissions=True)

	def test_creation_copies_required_project_number(self):
		for fieldname in ("custom_project_no", "project_no", "custom_reference"):
			with self.subTest(fieldname=fieldname):
				self.doc.pop("project", None)
				self.project.reset_mock()
				self.project_meta.fields = [Doc(fieldname=fieldname, label="Project No")]
				with patch.object(api.frappe.db, "exists", return_value=False), patch.object(
					api.frappe, "get_doc", return_value=self.project
				):
					api.on_submit(self.doc)
				self.project.set.assert_called_once_with(fieldname, "P-1")
				self.project.insert.assert_called_once_with(ignore_permissions=True)

	def test_reused_project_receives_required_number_before_save(self):
		self.doc.project = self.project.name
		self.project.project_name = "P-1"
		self.project.get.side_effect = {"customer": "Customer", "company": "Company", "sales_order": "SO-1"}.get
		self.project_meta.fields = [Doc(fieldname="custom_project_no", label="Project No")]
		with patch.object(api.frappe, "get_doc", return_value=self.project):
			api.on_submit(self.doc)
		self.project.set.assert_called_once_with("custom_project_no", "P-1")
		self.project.save.assert_called_once_with(ignore_permissions=True)
