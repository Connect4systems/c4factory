import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	derived = {"custom_color_sample_data", "custom_wood_color_doctype", "custom_wood", "custom_metal"}
	for field in frappe.get_meta("Sales Order Item").fields:
		is_part_list = field.fieldtype == "Link" and field.options == "Part List"
		if is_part_list or field.fieldname in derived:
			make_property_setter("Sales Order Item", field.fieldname, "allow_on_submit", 1, "Check")
		if is_part_list:
			make_property_setter("Sales Order Item", field.fieldname, "read_only", 0, "Check")
	frappe.clear_cache(doctype="Sales Order Item")
