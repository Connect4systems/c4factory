import frappe
from frappe.utils import now_datetime, today

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
		if row.get("part_list") or row.get("custom_part_list"):
			continue
		if row.item_code not in item_cache:
			item_cache[row.item_code] = frappe.db.get_value(
				"Item", row.item_code, ["item_name", "image"], as_dict=True
			) or {}
		details = item_cache[row.item_code]
		values = {
			"sales_order_item": row.name,
			"item": row.item_code,
			"item_name": details.get("item_name"),
			"image": details.get("image"),
			"description": row.description,
			"qty": row.qty,
		}
		for source_field, target_field in SALES_ORDER_ITEM_SPEC_FIELD_MAP.items():
			values[target_field] = row.get(source_field)
		target.append("items", values)
	return target


def update_sales_order_part_list(part_list):
	"""Update only the originating row, including on submitted Sales Orders."""
	meta = frappe.get_meta("Sales Order Item")
	link_fields = [field.fieldname for field in meta.fields
		if field.fieldtype == "Link" and field.options == "Part List"]
	if not link_fields:
		return
	for request_row in frappe.get_all(
		"PDS Request Item", filters={"part_list": part_list.name, "parenttype": "PDS Request"},
		fields=["parent", "item", "sales_order_item"],
	):
		if request_row.item != part_list.product:
			continue
		request = frappe.db.get_value("PDS Request", request_row.parent, ["sales_order", "docstatus"], as_dict=True)
		if not request or not request.sales_order or request.docstatus == 2:
			continue
		status = frappe.db.get_value("Sales Order", request.sales_order, "docstatus")
		if status is None or status == 2:
			continue
		filters = {"parent": request.sales_order, "parenttype": "Sales Order", "item_code": part_list.product}
		if request_row.sales_order_item:
			filters["name"] = request_row.sales_order_item
		rows = frappe.get_all("Sales Order Item", filters=filters, fields=["name"])
		# Older requests lack row references: use the item only when unambiguous.
		if len(rows) != 1:
			continue
		frappe.db.set_value("Sales Order Item", rows[0].name, {field: part_list.name for field in link_fields})
		frappe.db.set_value("Sales Order", request.sales_order, "modified", now_datetime())
