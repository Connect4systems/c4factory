"""Remove retired Item color metadata while retaining historical database columns."""
import json

import frappe

FIELDS = ("custom_color", "custom_color_doctype", "custom_basic_color",
          "custom_material_color_doctype", "custom_material_color")


def execute():
    for name in frappe.get_all("Property Setter", filters={
        "doc_type": "Item", "field_name": ["in", FIELDS],
    }, pluck="name"):
        frappe.delete_doc("Property Setter", name, ignore_permissions=True)
    for name in frappe.get_all("Custom Field", filters={
        "dt": "Item", "fieldname": ["in", FIELDS],
    }, pluck="name"):
        frappe.delete_doc("Custom Field", name, ignore_permissions=True)
    for setter in frappe.get_all("Property Setter", filters={
        "doc_type": "Item", "property": "field_order",
    }, fields=["name", "value"]):
        order = json.loads(setter.value or "[]")
        frappe.db.set_value("Property Setter", setter.name, "value",
                            json.dumps([field for field in order if field not in FIELDS]))
    frappe.clear_cache(doctype="Item")
