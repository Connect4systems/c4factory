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
	def validate(self):
		company = get_request_company(self.sales_order)
		for row in self.items:
			if not row.bom:
				continue
			bom = frappe.db.get_value("BOM", row.bom, ["item", "company", "is_active", "docstatus"], as_dict=True)
			if not bom or bom.item != row.item or bom.company != company or not bom.is_active or bom.docstatus == 2:
				frappe.throw(f"Row {row.idx}: select an active, non-cancelled BOM for this Item and company.")


def get_request_company(sales_order=None):
	company = frappe.db.get_value("Sales Order", sales_order, "company") if sales_order else None
	return company or frappe.defaults.get_user_default("Company") or frappe.db.get_default("company")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_boms(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe._dict(filters or {})
	if not filters.item:
		return []
	return frappe.get_list(
		"BOM",
		filters={
			"item": filters.item,
			"company": get_request_company(filters.sales_order),
			"is_active": 1,
			"docstatus": ["<", 2],
			"name": ["like", f"%{txt}%"],
		},
		fields=["name", "item"],
		order_by="modified desc",
		start=start,
		page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
def create_bom_for_item(item, qty=1, company=None, contract_bom_request=None, contract_bom_item=None):
	if not item:
		frappe.throw("Please set Item before creating BOM.")

	item_doc = frappe.get_cached_doc("Item", item)

	contract_row = None
	if contract_bom_request and contract_bom_item:
		request_doc = frappe.get_doc("Contract BOM Request", contract_bom_request)
		request_doc.check_permission("write")
		if request_doc.docstatus != 0:
			frappe.throw("BOM links can only be changed on a draft Contract BOM Request.")
		company = get_request_company(request_doc.sales_order)
		contract_row = frappe.db.get_value(
			"Contract BOM Item",
			contract_bom_item,
			["parent", "parenttype", "item", *CONTRACT_BOM_TO_BOM_FIELD_MAP],
			as_dict=True,
		)
		if (
			not contract_row
			or contract_row.parenttype != "Contract BOM Request"
			or contract_row.parent != contract_bom_request
		):
			frappe.throw("Invalid Contract BOM row selected.")
		if contract_row.item != item:
			frappe.throw("The selected Item does not match the saved Contract BOM row.")

	if not company:
		company = get_request_company()
	if not company:
		frappe.throw("Please set a default Company or link a Sales Order with a Company before creating BOM.")

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

	return bom.name
