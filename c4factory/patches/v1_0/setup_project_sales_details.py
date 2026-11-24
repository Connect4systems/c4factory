"""Fetch Project sales details from its linked Sales Order."""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	create_custom_fields({
		"Project": [
			{"fieldname": "custom_project_title", "label": "Project Title", "fieldtype": "Data",
			 "insert_after": "project_name", "fetch_from": "sales_order.custom_project_title",
			 "fetch_if_empty": 0},
			{"fieldname": "custom_sales_partner", "label": "Sales Partner", "fieldtype": "Link",
			 "options": "Sales Partner", "insert_after": "customer",
			 "fetch_from": "sales_order.sales_partner", "fetch_if_empty": 0},
		],
	}, update=True)
	meta = frappe.get_meta("Project", cached=False)
	order = [field.fieldname for field in meta.fields if field.fieldname != "custom_sales_partner"]
	order.insert(order.index("customer") + 1, "custom_sales_partner")
	make_property_setter("Project", None, "field_order", json.dumps(order), "Data", for_doctype=True)
	frappe.clear_cache(doctype="Project")
