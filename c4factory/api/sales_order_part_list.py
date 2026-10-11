from types import SimpleNamespace

import frappe
from frappe import _


def check_part_list_change(sales_order, item_name):
	# Share the submission lock used by Color Samples to avoid concurrent changes.
	frappe.db.sql("select name from `tabSales Order` where name = %s for update", sales_order)
	issued = frappe.db.sql(
		"""select s.name from `tabColor sample` s
		inner join `tabColor Sample Item` i on i.parent = s.name
		where s.sales_order = %s and s.docstatus = 1
		and i.parenttype = 'Color sample' and i.parentfield = 'items'
		and i.sales_order_item = %s limit 1 for update""",
		(sales_order, item_name),
	)
	if issued:
		frappe.throw(_("Cancel Color Sample {0} before changing this Sales Order item's Part List.").format(issued[0][0]))


def before_update_after_submit(doc, method=None):
	previous = doc.get_doc_before_save()
	if not previous:
		return
	fields = [field.fieldname for field in frappe.get_meta("Sales Order Item").fields
		if field.fieldtype == "Link" and field.options == "Part List"]
	old_rows = {row.name: row for row in previous.items}
	changed = []
	for row in doc.items:
		old = old_rows.get(row.name)
		if old and any((row.get(field) or "") != (old.get(field) or "") for field in fields):
			check_part_list_change(doc.name, row.name)
			for field in fields:
				part_list = row.get(field)
				if not part_list:
					continue
				part = frappe.get_doc("Part List", part_list)
				if part.docstatus != 1 or part.get("disable") or part.product != row.item_code:
					frappe.throw(_("Row {0}: Select an enabled, submitted Part List for item {1}.").format(row.idx, row.item_code))
			# Rebuild defaults rather than retaining colors from the previous Part List.
			row.custom_color_sample_data = None
			row.custom_wood_color_doctype = None
			changed.append(row)
	if changed:
		from c4factory.api.sales_order_colors import validate_colors
		validate_colors(SimpleNamespace(items=changed))
