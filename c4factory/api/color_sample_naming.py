"""Color Sample numbering by Sales Order project number and item name."""

import frappe
from frappe import _
from frappe.model.naming import getseries


def set_sample_name(doc):
	order = frappe.get_doc("Sales Order", doc.sales_order)
	order.check_permission("read")
	project_no = (order.get("custom_project_no") or "").strip()
	if not project_no and order.get("project"):
		project = frappe.get_doc("Project", order.project)
		project_no = (project.get("custom_project_no") or project.get("project_no")
			or project.get("project_name") or "").strip()
	if not project_no:
		frappe.throw(_("Set the Sales Order Project No before creating a Color Sample."))
	rows = doc.get("items") or []
	if not rows:
		frappe.throw(_("Select at least one Sales Order item."))
	source = next((row for row in order.get("items") or []
		if row.name == rows[0].sales_order_item), None)
	if not source:
		frappe.throw(_("The first Color Sample item must belong to its Sales Order."))
	item_name = (frappe.db.get_value("Item", source.item_code, "item_name") or "").strip()
	if not item_name:
		frappe.throw(_("Set the item name before creating a Color Sample."))
	# The dot before ## is naming-series syntax, not part of the resulting name.
	prefix = f"{project_no}-{item_name}-"
	doc.name = prefix + getseries(prefix, 2)
