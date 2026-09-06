# Copyright (c) 2025, Connect 4 Systems and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from c4factory.c4factory.doctype.contract_bom_request.contract_bom_request import (
	ContractBOMRequest,
	create_bom_for_item,
	get_request_company,
)

MODULE = "c4factory.c4factory.doctype.contract_bom_request.contract_bom_request"


class TestContractBOMRequest(FrappeTestCase):
	def test_company_resolution(self):
		for sales_company, user_company, global_company, expected in (
			("Sales Company", "User Company", "Global Company", "Sales Company"),
			(None, "User Company", "Global Company", "User Company"),
			(None, None, "Global Company", "Global Company"),
			(None, None, None, None),
		):
			with self.subTest(expected=expected), patch("frappe.db.get_value", return_value=sales_company), patch(
				"frappe.defaults.get_user_default", return_value=user_company
			), patch("frappe.db.get_default", return_value=global_company):
				self.assertEqual(get_request_company("SO-TEST"), expected)

	def test_matching_draft_and_submitted_boms_are_allowed(self):
		request = frappe._dict(sales_order="SO-TEST")
		request.items = [frappe._dict(idx=1, item="ITEM-A", bom="BOM-A")]
		for status in (0, 1):
			with self.subTest(status=status), patch(f"{MODULE}.get_request_company", return_value="Company A"), patch(
				"frappe.db.get_value",
				return_value=frappe._dict(item="ITEM-A", company="Company A", is_active=1, docstatus=status),
			):
				ContractBOMRequest.validate(request)

	def test_invalid_bom_links_are_rejected(self):
		request = frappe._dict(sales_order="SO-TEST")
		request.items = [frappe._dict(idx=1, item="ITEM-A", bom="BOM-A")]
		for mismatch in ({"item": "ITEM-B"}, {"company": "Company B"}, {"is_active": 0}, {"docstatus": 2}):
			bom = frappe._dict(item="ITEM-A", company="Company A", is_active=1, docstatus=0)
			bom.update(mismatch)
			with self.subTest(mismatch=mismatch), patch(f"{MODULE}.get_request_company", return_value="Company A"), patch(
				"frappe.db.get_value", return_value=bom
			):
				with self.assertRaises(frappe.ValidationError):
					ContractBOMRequest.validate(request)

	def test_create_rejects_submitted_request(self):
		from unittest.mock import Mock

		request = Mock(docstatus=1)
		with patch("frappe.get_cached_doc"), patch("frappe.get_doc", return_value=request):
			with self.assertRaises(frappe.ValidationError):
				create_bom_for_item("ITEM-A", company="Company A", contract_bom_request="REQ-A", contract_bom_item="ROW-A")
