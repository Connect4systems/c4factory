"""Detach editable order/request references before cancelling a Part List."""

import frappe
from frappe import _


@frappe.whitelist()
def unlink_part_list(name):
	part = frappe.get_doc("Part List", name)
	part.check_permission("write")
	if part.docstatus == 1:
		part.check_permission("cancel")
	else:
		part.check_permission("delete")
	return unlink_references(part)


def unlink_references(part):
	# Collect and authorize every change before writing any of them.
	changes = []
	for parenttype, childtype in (
		("Sales Order", "Sales Order Item"), ("PDS Request", "PDS Request Item"),
	):
		meta = frappe.get_meta(childtype)
		fields = [df.fieldname for df in meta.fields
			if df.fieldtype == "Link" and df.options == "Part List"]
		rows = {}
		for field in fields:
			for row in frappe.get_all(childtype, filters={
				"parenttype": parenttype, field: part.name,
			}, fields=["name", "parent", *fields]):
				rows[row.name] = row
		for parent in sorted({row.parent for row in rows.values()}):
			frappe.db.sql(f"select name from `tab{parenttype}` where name = %s for update", parent)
			frappe.get_doc(parenttype, parent).check_permission("write")
		for row in rows.values():
			if parenttype == "Sales Order":
				from c4factory.api.sales_order_part_list import check_part_list_change

				check_part_list_change(row.parent, row.name)
			values = {field: None for field in fields if row.get(field) == part.name}
			if parenttype == "Sales Order" and meta.has_field("custom_color_sample_data"):
				values["custom_color_sample_data"] = None
			changes.append((parenttype, childtype, row, values))
	for parenttype, childtype, row, values in changes:
		frappe.db.set_value(childtype, row.name, values, update_modified=False)
	for parenttype, parent in sorted({(pt, row.parent) for pt, _, row, _ in changes}):
		frappe.db.set_value(parenttype, parent, "modified", frappe.utils.now())
		frappe.get_doc(parenttype, parent).notify_update()
	return len(changes)
