import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """
    Create custom fields for Pick List and Stock Entry integration.
    
    Custom fields created:
    - Pick List: c4_work_order, c4_status, c4_balance fields
    - Pick List Item: c4_wo_required_qty, c4_balance_qty, c4_consumed_qty
    - Stock Entry: c4_pick_list
    """
    
    custom_fields = {
        "Pick List": [
            {
                "fieldname": "c4_work_order",
                "label": "Work Order",
                "fieldtype": "Link",
                "options": "Work Order",
                "insert_after": "purpose",
                "allow_on_submit": 0,
                "read_only": 0,
                "in_list_view": 1,
                "in_standard_filter": 1,
            },
            {
                "fieldname": "c4_status",
                "label": "C4 Status",
                "fieldtype": "Select",
                "options": "Open\nCompleted",
                "default": "Open",
                "insert_after": "c4_work_order",
                "allow_on_submit": 1,
                "read_only": 1,
                "in_list_view": 1,
                "in_standard_filter": 1,
            },
            {
                "fieldname": "c4_balance_section",
                "label": "Balance Summary",
                "fieldtype": "Section Break",
                "insert_after": "c4_status",
                "collapsible": 1,
            },
            {
                "fieldname": "c4_total_qty",
                "label": "Total Qty",
                "fieldtype": "Float",
                "insert_after": "c4_balance_section",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "c4_consumed_qty",
                "label": "Consumed Qty",
                "fieldtype": "Float",
                "insert_after": "c4_total_qty",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "c4_balance_qty",
                "label": "Balance Qty",
                "fieldtype": "Float",
                "insert_after": "c4_consumed_qty",
                "read_only": 1,
                "allow_on_submit": 1,
                "bold": 1,
            },
        ],
        "Pick List Item": [
            {
                "fieldname": "c4_wo_required_qty",
                "label": "WO Required Qty",
                "fieldtype": "Float",
                "insert_after": "qty",
                "allow_on_submit": 1,
                "read_only": 1,
                "in_list_view": 0,
            },
            {
                "fieldname": "c4_balance_qty",
                "label": "Balance Qty",
                "fieldtype": "Float",
                "insert_after": "c4_wo_required_qty",
                "allow_on_submit": 1,
                "read_only": 1,
                "in_list_view": 1,
                "description": "Remaining quantity to be consumed in Stock Entries",
            },
            {
                "fieldname": "c4_consumed_qty",
                "label": "Consumed Qty",
                "fieldtype": "Float",
                "insert_after": "c4_balance_qty",
                "allow_on_submit": 1,
                "read_only": 1,
                "in_list_view": 1,
                "description": "Quantity consumed in Stock Entries",
            },
        ],
        "Stock Entry": [
            {
                "fieldname": "c4_pick_list",
                "label": "C4 Pick List",
                "fieldtype": "Link",
                "options": "Pick List",
                "insert_after": "work_order",
                "allow_on_submit": 0,
                "read_only": 0,
                "in_list_view": 0,
                "in_standard_filter": 1,
                "description": "Pick List from which this Stock Entry was created",
            },
        ],
    }
    
    create_custom_fields(custom_fields, update=True)
