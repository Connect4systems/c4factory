import frappe
from frappe.utils import today

from c4factory.api.contract_bom import SALES_ORDER_ITEM_SPEC_FIELD_MAP


@frappe.whitelist()
def make_pds_request(sales_order: str):
	source = frappe.get_doc("Sales Order", sales_order)
	source.check_permission("read")
	target = frappe.new_doc("PDS Request")
	target.check_permission("create")
	target.sales_order = source.name
	target.customer = source.customer
	target.date = today()
	item_cache = {}
	for row in sorted(source.items, key=lambda row: row.idx or 0):
		if row.item_code not in item_cache:
			item_cache[row.item_code] = frappe.db.get_value(
				"Item", row.item_code, ["item_name", "image"], as_dict=True
			) or {}
		details = item_cache[row.item_code]
		values = {
			"item": row.item_code,
			"item_name": details.get("item_name"),
			"image": details.get("image"),
			"description": row.description,
			"qty": row.qty,
			"part_list": row.get("part_list") or row.get("custom_part_list"),
		}
		for source_field, target_field in SALES_ORDER_ITEM_SPEC_FIELD_MAP.items():
			values[target_field] = row.get(source_field)
		target.append("items", values)
	return target
