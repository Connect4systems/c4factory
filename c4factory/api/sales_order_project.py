import frappe
from frappe import _


def before_submit(doc, method=None):
	project_name = (doc.get("custom_project_no") or "").strip()
	if not project_name:
		frappe.throw(_("Project No is required before submitting the Sales Order."))
	doc.custom_project_no = project_name

	if doc.get("project"):
		project = frappe.get_doc("Project", doc.project)
		if (
			project.project_name != project_name
			or project.get("customer") != doc.customer
			or project.get("company") != doc.company
			or project.get("sales_order") not in {value for value in (doc.name, doc.get("amended_from")) if value}
		):
			frappe.throw(_("The linked Project must match Project No, customer, company and Sales Order."))
		project.sales_order = doc.name
		project.save(ignore_permissions=True)
		return

	if frappe.db.exists("Project", {"project_name": project_name}):
		frappe.throw(_("A Project named {0} already exists. Enter a unique Project No.").format(project_name))

	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": project_name,
		"sales_order": doc.name,
		"customer": doc.customer,
		"company": doc.company,
		"status": "Open",
	})
	# Project creation is part of the authorized Sales Order submission transaction.
	project.insert(ignore_permissions=True)
	doc.project = project.name
