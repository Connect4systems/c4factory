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
