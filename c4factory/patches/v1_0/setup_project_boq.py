import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	project_number = {
		"fieldname": "custom_project_no", "label": "Project No", "fieldtype": "Data",
		"insert_after": "project_name", "read_only": 1,
	}
	legacy_type = frappe.db.get_value(
		"Custom Field", {"dt": "Project", "fieldname": "custom_project_no"}, "fieldtype",
	)
	if legacy_type == "Float":
		# Older sites stored Project No as a number. Widen this one column to text
		# through Frappe's schema updater, preserving its existing numeric values.
		# Float -> Data is blocked by Custom Field's interactive validation, so
		# bypass it only for this known conversion, not for the remaining fields.
		create_custom_fields({"Project": [project_number]}, ignore_validate=True, update=True)
	create_custom_fields({
		"Project": [
			project_number,
			{"fieldname": "custom_technical_team", "label": "Technical Team", "fieldtype": "Link",
			 "options": "Technical Team", "insert_after": "custom_project_no"},
			{"fieldname": "custom_project_boq_tab", "label": "Project BOQ", "fieldtype": "Tab Break"},
			{"fieldname": "custom_project_boq", "label": "Items", "fieldtype": "Table",
			 "options": "Project BOQ Item", "insert_after": "custom_project_boq_tab",
			 "no_copy": 1},
		],
		"Installation Note": [
			{"fieldname": "custom_project", "label": "Project", "fieldtype": "Link",
			 "options": "Project", "insert_after": "customer", "read_only": 1},
		],
	}, update=True)
