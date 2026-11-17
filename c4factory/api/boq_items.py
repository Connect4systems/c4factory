"""Item eligibility shared by PDS fetching and the Part List product picker."""

import frappe


def boq_item_filters():
	fields = [field.fieldname for field in frappe.get_meta("Item").fields
		if field.fieldtype == "Link" and field.options == "Item Type"]
	if len(fields) != 1:
		frappe.throw("Item must have one Item Type link field to filter BOQ products.")
	types = frappe.get_all("Item Type", filters={"boq_required": 1}, pluck="name")
	return {fields[0]: ["in", types]}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_part_list_products(doctype, txt, searchfield, start, page_len, filters=None):
	item_filters = boq_item_filters()
	item_filters.update({"disabled": 0, "is_sales_item": 1})
	return frappe.get_list(
		"Item", filters=item_filters,
		or_filters={"name": ["like", f"%{txt}%"], "item_name": ["like", f"%{txt}%"]},
		fields=["name", "item_name"], order_by="name asc",
		start=start, page_length=page_len, as_list=True,
	)
