import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	# The parent table must permit updates as well as its individual link fields.
	make_property_setter("Sales Order", "items", "allow_on_submit", 1, "Check")
	make_property_setter("Sales Order", "items", "read_only", 0, "Check")
	derived = {"custom_color_sample_data"}
	for field in frappe.get_meta("Sales Order Item").fields:
		is_part_list = field.fieldtype == "Link" and field.options == "Part List"
		if is_part_list or field.fieldname in derived:
			make_property_setter("Sales Order Item", field.fieldname, "allow_on_submit", 1, "Check")
		if is_part_list:
			make_property_setter("Sales Order Item", field.fieldname, "read_only", 0, "Check")
			make_property_setter("Sales Order Item", field.fieldname, "reqd", 0, "Check")
			make_property_setter("Sales Order Item", field.fieldname, "read_only_depends_on", "", "Data")
			make_property_setter("Sales Order Item", field.fieldname, "mandatory_depends_on", "", "Data")
	frappe.clear_cache(doctype="Sales Order Item")
	frappe.clear_cache(doctype="Sales Order")
