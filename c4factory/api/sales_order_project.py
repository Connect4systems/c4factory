import frappe
from frappe import _


def set_project_number(project, project_no):
	# Project customizations can come from the site or another installed app.
	for field in frappe.get_meta("Project").fields:
		if field.fieldname in {"custom_project_no", "project_no"} or field.label == "Project No":
			project.set(field.fieldname, project_no)


def on_submit(doc, method=None):
	# Workflow requests must not create projects while the order is still a draft.
	if doc.docstatus != 1:
		return
	project_name = (doc.get("custom_project_no") or "").strip()
	if not project_name:
		frappe.throw(_("Project No is required before submitting the Sales Order."))
	doc.custom_project_no = project_name

	def matches(project):
		return (
			project.project_name == project_name
			and project.get("customer") == doc.customer
			and project.get("company") == doc.company
			and (not project.get("sales_order") or project.get("sales_order") in
				{doc.name, doc.get("amended_from")})
		)

	project = frappe.get_doc("Project", doc.project) if doc.get("project") else None
	if project is None or not matches(project):
		# An old/manual link must not prevent creating the order's own Project.
		existing = frappe.db.exists("Project", {"project_name": project_name})
		project = frappe.get_doc("Project", existing) if existing else None
		if project is not None and not matches(project):
			frappe.throw(_("A Project named {0} belongs to another customer, company or Sales Order. Enter a unique Project No.").format(project_name))

	if project is not None:
		project.sales_order = doc.name
		set_project_number(project, project_name)
		project.save(ignore_permissions=True)
		doc.db_set({"project": project.name, "custom_project_no": project_name}, update_modified=False)
		return

	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": project_name,
		"sales_order": doc.name,
		"customer": doc.customer,
		"company": doc.company,
		"status": "Open",
	})
	set_project_number(project, project_name)
	# Project creation is part of the authorized Sales Order submission transaction.
	project.insert(ignore_permissions=True)
	# on_submit runs after the Sales Order has been written; persist the link too.
	doc.db_set({"project": project.name, "custom_project_no": project_name}, update_modified=False)
