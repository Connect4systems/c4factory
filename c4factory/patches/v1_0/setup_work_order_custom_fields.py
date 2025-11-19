import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """
    Create Work Order custom fields for:
      - C4 Required Items (editable items from BOM)
      - C4 Scrap & Process Loss tab
      - C4 Costing tab
    """

    custom_fields = {
        "Work Order": [
            # --- C4 Required Items tab (NEW) ---
            {
                "fieldname": "c4_required_items_tab",
                "label": "C4 Required Items",
                "fieldtype": "Tab Break",
                "insert_after": "required_items",
            },
            {
                "fieldname": "c4_required_items",
                "label": "Required Items (Editable)",
                "fieldtype": "Table",
                "options": "Work Order Item",
                "insert_after": "c4_required_items_tab",
                "allow_on_submit": 0,
                "description": "Editable required items for this Work Order. Initially copied from BOM.",
            },
            {
                "fieldname": "c4_items_section",
                "label": "Item Balance Summary",
                "fieldtype": "Section Break",
                "insert_after": "c4_required_items",
                "collapsible": 1,
            },
            {
                "fieldname": "c4_total_picked_qty",
                "label": "Total Picked Qty",
                "fieldtype": "Float",
                "insert_after": "c4_items_section",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "c4_total_consumed_qty",
                "label": "Total Consumed Qty",
                "fieldtype": "Float",
                "insert_after": "c4_total_picked_qty",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            
            # --- Scrap & Process Loss tab ---
            {
                "fieldname": "c4_scrap_process_tab",
                "label": "C4 Scrap & Process Loss",
                "fieldtype": "Tab Break",
                "insert_after": "operations",
            },
            {
                "fieldname": "c4_scrap_items",
                "label": "Scrap Items",
                "fieldtype": "Table",
                "options": "BOM Scrap Item",
                "insert_after": "c4_scrap_process_tab",
                "allow_on_submit": 1,
            },
            {
                "fieldname": "c4_process_loss_section",
                "label": "Process Loss",
                "fieldtype": "Section Break",
                "insert_after": "c4_scrap_items",
            },
            {
                "fieldname": "c4_process_loss_percent",
                "label": "% Process Loss",
                "fieldtype": "Float",
                "insert_after": "c4_process_loss_section",
                "allow_on_submit": 1,
            },
            {
                "fieldname": "c4_process_loss_qty",
                "label": "Process Loss Qty",
                "fieldtype": "Float",
                "insert_after": "c4_process_loss_percent",
                "allow_on_submit": 1,
            },

            # --- C4 Costing tab ---
            {
                "fieldname": "c4_costing_tab",
                "label": "C4 Costing",
                "fieldtype": "Tab Break",
                "insert_after": "c4_process_loss_qty",
            },
            {
                "fieldname": "c4_raw_material_cost",
                "label": "Raw Material Cost (EGP)",
                "fieldtype": "Currency",
                "insert_after": "c4_costing_tab",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "c4_operating_cost",
                "label": "Operating Cost (EGP)",
                "fieldtype": "Currency",
                "insert_after": "c4_raw_material_cost",
                "read_only": 0,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "c4_scrap_material_cost",
                "label": "Scrap Material Cost (EGP)",
                "fieldtype": "Currency",
                "insert_after": "c4_operating_cost",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "c4_total_cost",
                "label": "Total Cost (EGP)",
                "fieldtype": "Currency",
                "insert_after": "c4_scrap_material_cost",
                "read_only": 1,
                "allow_on_submit": 1,
            },
        ],
    }

    create_custom_fields(custom_fields, update=True)
