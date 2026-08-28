# Copyright (c) 2025, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


CONTRACT_BOM_TO_BOM_FIELD_MAP = {
	"image": "custom_item_image",
	"location_code": "custom_location_code",
	"sub_code": "custom_sub_code",
	"plexi": "custom_plexi",
	"top": "custom_top",
	"modesty": "custom_modesty",
	"wood": "custom_wood",
	"metal": "custom_metal",
	"leather": "custom_leather",
	"drawer_body": "custom_drawer_body",
	"drawer_face": "custom_drawer_face",
	"glass": "custom_glass",
	"fabric": "custom_fabric",
	"direction": "custom_direction",
	"other": "custom_other",
	"additional_notes": "custom_additional_notes",
}


class ContractBOMRequest(Document):
	pass


@frappe.whitelist()
def create_bom_for_item(item, qty=1, company=None, contract_bom_request=None, contract_bom_item=None):
	if not item:
		frappe.throw("Please set Item before creating BOM.")

	if not company:
		company = frappe.defaults.get_default("company")

	item_doc = frappe.get_cached_doc("Item", item)

	contract_row = None
	if contract_bom_request and contract_bom_item:
		request_doc = frappe.get_doc("Contract BOM Request", contract_bom_request)
		request_doc.check_permission("write")
		contract_row = frappe.db.get_value(
			"Contract BOM Item",
			contract_bom_item,
			["parent", "parenttype", *CONTRACT_BOM_TO_BOM_FIELD_MAP],
			as_dict=True,
		)
		if (
			not contract_row
			or contract_row.parenttype != "Contract BOM Request"
			or contract_row.parent != contract_bom_request
		):
			frappe.throw("Invalid Contract BOM row selected.")

	bom_values = {
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
	}
	if contract_row:
		for source_field, target_field in CONTRACT_BOM_TO_BOM_FIELD_MAP.items():
			bom_values[target_field] = contract_row.get(source_field)

	bom = frappe.get_doc(bom_values)
	bom.insert(ignore_permissions=False)

	if contract_row:
		# Persist link on child row so dashboard internal link can resolve exact BOM names.
		frappe.db.set_value("Contract BOM Item", contract_bom_item, "bom", bom.name, update_modified=False)

	frappe.db.commit()
	return bom.name
