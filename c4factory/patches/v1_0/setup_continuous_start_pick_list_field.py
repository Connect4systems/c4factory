import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Pick List": [
                {
                    "fieldname": "custom_continuous_start_request_id",
                    "label": "Continuous Start Request ID",
                    "fieldtype": "Data",
                    "hidden": 1,
                    "read_only": 1,
                    "no_copy": 1,
                    "unique": 1,
                },
            ],
        },
        update=True,
    )
