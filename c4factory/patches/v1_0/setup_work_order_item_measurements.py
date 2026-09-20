import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    measurements = [
        ("custom_unit_qty", "Unit Qty"),
        ("custom_width", "Width"),
        ("custom_height", "Height"),
        ("custom_depth", "Depth"),
    ]
    names = {name for name, label in measurements}
    existing = [field.fieldname for field in frappe.get_meta("Work Order Item").fields
                if field.fieldname not in names]
    insert_after = existing[existing.index("required_qty") - 1]
    fields = []
    for name, label in measurements:
        fields.append({
            "fieldname": name, "label": label, "fieldtype": "Float",
            "insert_after": insert_after, "in_list_view": 1,
            "columns": 1, "read_only": 1,
        })
        insert_after = name
    create_custom_fields({"Work Order Item": fields}, update=True)

