import json

import frappe

REMOVED_FIELDS = {"custom_wood", "custom_metal", "custom_wood_color_doctype"}


def execute():
	"""Remove obsolete Sales Order item color controls after customization sync."""
	fields = frappe.get_all(
		"Custom Field", filters={"dt": "Sales Order Item"},
		fields=["name", "fieldname", "insert_after"],
	)
	anchors = {field.fieldname: field.insert_after for field in fields}
	for field in fields:
		if field.fieldname in REMOVED_FIELDS:
			continue
		anchor = field.insert_after
		visited = set()
		while anchor in REMOVED_FIELDS and anchor not in visited:
			visited.add(anchor)
			anchor = anchors.get(anchor)
		if anchor != field.insert_after:
			frappe.db.set_value("Custom Field", field.name, "insert_after", anchor)

	for setter in frappe.get_all(
		"Property Setter", filters={"doc_type": "Sales Order Item"},
		fields=["name", "field_name", "property", "value"],
	):
		if setter.field_name in REMOVED_FIELDS:
			frappe.delete_doc("Property Setter", setter.name, ignore_permissions=True)
		elif setter.property == "field_order":
			order = json.loads(setter.value)
			cleaned = [name for name in order if name not in REMOVED_FIELDS]
			if cleaned != order:
				frappe.db.set_value("Property Setter", setter.name, "value", json.dumps(cleaned))

	for field in fields:
		if field.fieldname in REMOVED_FIELDS:
			frappe.delete_doc("Custom Field", field.name, ignore_permissions=True)
	frappe.clear_cache(doctype="Sales Order Item")
