from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields({
        "Work Order Item": [{
            "fieldname": "custom_part_type",
            "label": "Part Type",
            "fieldtype": "Link",
            "options": "Part Type",
            "insert_after": "item_name",
            "in_list_view": 1,
            "columns": 1,
            "read_only": 1,
        }],
    }, update=True)
