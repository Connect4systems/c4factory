import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	boq_fields = ["custom_project_boq_tab", "custom_project_boq_section", "custom_project_boq"]
	meta = frappe.get_meta("Project", cached=False)
	other_fields = [f.fieldname for f in meta.fields if f.fieldname not in boq_fields]
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
			{"fieldname": "custom_project_boq_tab", "label": "Project BOQ", "fieldtype": "Tab Break",
			 "insert_after": other_fields[-1], "hidden": 0},
			{"fieldname": "custom_project_boq_section", "fieldtype": "Section Break",
			 "insert_after": "custom_project_boq_tab"},
			{"fieldname": "custom_project_boq", "label": "Items", "fieldtype": "Table",
			 "options": "Project BOQ Item", "insert_after": "custom_project_boq_section",
			 "no_copy": 1},
		],
		"Installation Note": [
			{"fieldname": "custom_project", "label": "Project", "fieldtype": "Link",
			 "options": "Project", "insert_after": "customer", "read_only": 1},
		],
	}, update=True)
	# A site's Customize Form field_order takes precedence over insert_after.
	# Retain its other fields, then move the whole BOQ block to a final full-width tab.
	meta = frappe.get_meta("Project", cached=False)
	field_order = [f.fieldname for f in meta.fields if f.fieldname not in boq_fields] + boq_fields
	if [f.fieldname for f in meta.fields] != field_order:
		make_property_setter("Project", None, "field_order", json.dumps(field_order), "Data", for_doctype=True)
	frappe.clear_cache(doctype="Project")
