import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	# Preserve the site's existing Item Group configuration and field layout.
	if not frappe.get_meta("Item Group").has_field("custom_color"):
		create_custom_fields({"Item Group": [{
			"fieldname": "custom_color",
			"label": "Color",
			"fieldtype": "Link",
			"options": "DocType",
			"insert_after": "item_group_name",
		}]})
	create_custom_fields({"Item": [
		{
			"fieldname": "custom_material_color_doctype",
			"label": "Material Color DocType",
			"fieldtype": "Link",
			"options": "DocType",
			"hidden": 1,
			"read_only": 1,
			"depends_on": "",
			"insert_after": "item_group",
		},
		{
			"fieldname": "custom_material_color",
			"label": "Material Color",
			"fieldtype": "Dynamic Link",
			"options": "custom_material_color_doctype",
			"hidden": 0,
			"read_only": 0,
			"depends_on": "",
			"insert_after": "custom_material_color_doctype",
			"read_only_depends_on": "eval:!doc.custom_material_color_doctype",
		},
	]}, update=True)
