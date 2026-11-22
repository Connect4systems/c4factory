"""Install fields and backfill existing submitted contracts without workflows."""
import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def setup_fields():
    create_custom_fields({
        "Sales Order": [{"fieldname": "custom_project_title", "label": "Project Title",
            "fieldtype": "Data", "insert_after": "custom_project_no", "allow_on_submit": 1}],
        "Project": [{"fieldname": "custom_project_title", "label": "Project Title",
            "fieldtype": "Data", "insert_after": "project_name"}],
        "Sales Order Item": [
            {"fieldname": "custom_note", "label": "Note", "fieldtype": "Small Text",
                "insert_after": "description", "allow_on_submit": 1, "in_list_view": 1},
            {"fieldname": "custom_note_initialized", "fieldtype": "Check", "hidden": 1,
                "insert_after": "custom_note", "allow_on_submit": 1, "no_copy": 1},
        ],
    }, update=True)
    make_property_setter("Sales Order", "items", "allow_on_submit", 1, "Check")
    for doctype, fieldname, anchor in (
        ("Sales Order", "custom_project_title", "custom_project_no"),
        ("Project", "custom_project_title", "project_name"),
        ("Sales Order Item", "custom_note", "description"),
    ):
        order = [f.fieldname for f in frappe.get_meta(doctype, cached=False).fields if f.fieldname != fieldname]
        order.insert(order.index(anchor) + 1, fieldname)
        make_property_setter(doctype, None, "field_order", json.dumps(order), "Data", for_doctype=True)
        frappe.clear_cache(doctype=doctype)


def execute():
    setup_fields()
    from c4factory.api.quotation_project_details import fill_sales_order
    from c4factory.api.project_boq import build_rows, resolve_sales_order

    for name in frappe.get_all("Sales Order", filters={"docstatus": 1}, pluck="name"):
        doc = frappe.get_doc("Sales Order", name)
        fill_sales_order(doc)
        if doc.get("custom_project_title"):
            frappe.db.set_value("Sales Order", name, "custom_project_title", doc.custom_project_title, update_modified=False)
        for row in doc.items:
            frappe.db.set_value("Sales Order Item", row.name, {
                "custom_note": row.get("custom_note"),
                "custom_note_initialized": row.get("custom_note_initialized") or 0,
            }, update_modified=False)
    for name in frappe.get_all("Project", pluck="name"):
        project = frappe.get_doc("Project", name)
        if not resolve_sales_order(project):
            continue
        title = frappe.db.get_value("Sales Order", project.sales_order, "custom_project_title")
        values = {"sales_order": project.sales_order}
        if title and not project.get("custom_project_title"):
            values["custom_project_title"] = title
        frappe.db.set_value("Project", name, values, update_modified=False)
        project.set("custom_project_boq", build_rows(project))
        frappe.db.delete("Project BOQ Item", {"parent": name, "parenttype": "Project", "parentfield": "custom_project_boq"})
        for row in project.custom_project_boq:
            row.db_insert()
