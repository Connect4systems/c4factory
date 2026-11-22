"""Install delivery header details and row-level sales order notes."""
import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    create_custom_fields({
        "Delivery Note": [
            {"fieldname": "custom_project_no", "label": "Project No", "fieldtype": "Data",
             "insert_after": "custom_project_title", "read_only": 1,
             "fetch_from": "project.custom_project_no", "fetch_if_empty": 0},
            {"fieldname": "custom_project_title", "label": "Project Title", "fieldtype": "Data",
             "insert_after": "customer_name"},
            {"fieldname": "custom_technical_team", "label": "Technical Team", "fieldtype": "Link",
             "options": "Technical Team", "insert_after": "custom_project_no"},
        ],
        "Delivery Note Item": [
            {"fieldname": "custom_note", "label": "Note", "fieldtype": "Small Text",
             "insert_after": "description", "in_list_view": 1, "read_only": 0},
            {"fieldname": "custom_note_initialized", "fieldtype": "Check", "hidden": 1,
             "insert_after": "custom_note", "no_copy": 1},
        ],
    }, update=True)
    # Keep existing header note data while moving its visible replacement to items.
    for field in frappe.get_meta("Delivery Note", cached=False).fields:
        if field.fieldname in ("custom_note", "custom_sales_order_note") or (field.label or "").strip().lower() == "sales order note":
            make_property_setter("Delivery Note", field.fieldname, "hidden", 1, "Check")
    for doctype, fields, anchor in (
        ("Delivery Note", ["custom_project_title", "custom_project_no", "custom_technical_team"], "customer_name"),
        ("Delivery Note Item", ["custom_note", "custom_note_initialized"], "description"),
    ):
        order = [f.fieldname for f in frappe.get_meta(doctype, cached=False).fields if f.fieldname not in fields]
        index = order.index(anchor) + 1
        order[index:index] = fields
        make_property_setter(doctype, None, "field_order", json.dumps(order), "Data", for_doctype=True)
        frappe.clear_cache(doctype=doctype)
