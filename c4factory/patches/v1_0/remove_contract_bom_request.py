import frappe


def execute():
	# Remove the parent and its records before its private child table.
	for doctype in ("Contract BOM Request", "Contract BOM Item"):
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)
