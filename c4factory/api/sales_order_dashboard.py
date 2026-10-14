import frappe
from frappe import _

from erpnext.selling.doctype.sales_order.sales_order_dashboard import get_data as get_core_data


def get_data(*args, **kwargs):
	data = get_core_data()
	data.setdefault("non_standard_fieldnames", {})
	data["non_standard_fieldnames"]["PDS Request"] = "sales_order"
	data["non_standard_fieldnames"]["Color sample"] = "sales_order"
	# Part Lists are referenced by SO items, rather than pointing back to an SO.
	part_list_fields = [field.fieldname for field in frappe.get_meta("Sales Order Item").fields
		if field.fieldtype == "Link" and field.options == "Part List"]
	if part_list_fields:
		fieldname = "custom_part_list" if "custom_part_list" in part_list_fields else part_list_fields[0]
		data.setdefault("internal_links", {})["Part List"] = ["items", fieldname]

	transactions = data.setdefault("transactions", [])
	manufacturing_group = next(
		(group for group in transactions if group.get("label") == _("Manufacturing")),
		None,
	)
	if not manufacturing_group:
		manufacturing_group = {"label": _("Manufacturing"), "items": []}
		transactions.append(manufacturing_group)

	items = manufacturing_group.setdefault("items", [])
	if "PDS Request" not in items:
		items.append("PDS Request")
	if "Color sample" not in items:
		items.append("Color sample")
	if part_list_fields and "Part List" not in items:
		items.append("Part List")

	return data
