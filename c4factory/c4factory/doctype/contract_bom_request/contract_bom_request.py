# Copyright (c) 2025, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ContractBOMRequest(Document):
	pass


@frappe.whitelist()
def create_bom_for_item(item, qty=1, company=None):
	if not item:
		frappe.throw("Please set Item before creating BOM.")

	if not company:
		company = frappe.defaults.get_default("company")

	item_doc = frappe.get_cached_doc("Item", item)

	bom = frappe.get_doc({
		"doctype": "BOM",
		"item": item,
		"quantity": 1,
		"company": company,
		"items": [
			{
				"item_code": item,
				"qty": 1,
				"uom": item_doc.stock_uom,
			}
		],
	})
	bom.insert(ignore_permissions=False)
	frappe.db.commit()
	return bom.name
