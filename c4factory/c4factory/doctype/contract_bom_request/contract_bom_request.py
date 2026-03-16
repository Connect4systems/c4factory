# Copyright (c) 2025, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ContractBOMRequest(Document):
	pass


@frappe.whitelist()
def create_bom_for_item(item, qty=1, company=None):
	if not company:
		company = frappe.defaults.get_default("company")

	bom = frappe.get_doc({
		"doctype": "BOM",
		"item": item,
		"quantity": frappe.utils.flt(qty) or 1,
		"company": company,
	})
	bom.insert(ignore_permissions=False)
	frappe.db.commit()
	return bom.name
