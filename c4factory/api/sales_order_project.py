import frappe
from frappe import _


def set_project_number(project, project_no):
	for field in frappe.get_meta("Project").fields:
		if field.fieldname in {"custom_project_no", "project_no"} or field.label == "Project No":
			project.set(field.fieldname, project_no)


def on_submit(doc, method=None):
	if doc.docstatus != 1:
		return
	project_no = (doc.get("custom_project_no") or "").strip()
	if not project_no:
		frappe.throw(_("Project No is required before submitting the Sales Order."))
	frappe.db.sql("select name from `tabSales Order` where name=%s for update", doc.name)
	project = None
	legacy = frappe.db.exists("Project", {"custom_project_no": project_no})
	for candidate in dict.fromkeys(filter(None, [doc.get("project"), project_no, legacy])):
		if not frappe.db.exists("Project", candidate):
			continue
		current = frappe.get_doc("Project", candidate)
		if (current.customer == doc.customer and current.company == doc.company
			and current.get("sales_order") in {None, "", doc.name, doc.get("amended_from")}
			and (current.name == project_no or current.get("custom_project_no") == project_no
				or current.project_name == project_no)):
			project = current
			break
		if candidate in {project_no, legacy}:
			frappe.throw(_("Project No {0} already belongs to another Project.").format(project_no))
	if project is None:
		project = frappe.new_doc("Project")
		project.status = "Open"
	project.project_name = f"{project_no} \u2013 {doc.get('customer_name') or doc.customer}"
	project.customer = doc.customer
	project.company = doc.company
	project.sales_order = doc.name
	project.custom_technical_team = doc.get("custom_technical_team")
	project.custom_project_title = doc.get("custom_project_title")
	project.custom_sales_partner = doc.get("sales_partner")
	project.expected_start_date = doc.get("transaction_date")
	project.expected_end_date = doc.get("delivery_date")
	set_project_number(project, project_no)
	# Creation belongs to the authorized Sales Order submission transaction.
	if project.is_new():
		project.insert(ignore_permissions=True, set_name=project_no)
	else:
		project.save(ignore_permissions=True)
	doc.db_set({"project": project.name, "custom_project_no": project_no}, update_modified=False)
