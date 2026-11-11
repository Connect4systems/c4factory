"""Keep Part List descriptions in a rich text editor after customization sync."""
import frappe


def execute():
    # An existing Customize Form override must not turn HTML back into raw text.
    for setter in frappe.get_all("Property Setter", filters={
        "doc_type": "Part List", "field_name": "description", "property": "fieldtype",
    }, pluck="name"):
        frappe.db.set_value("Property Setter", setter, "value", "Text Editor")
    frappe.clear_cache(doctype="Part List")
