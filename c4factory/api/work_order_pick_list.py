import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def make_pick_list(work_order_id):
    """
    Create a Pick List from a Work Order based on c4_required_items.
    
    This function:
    1. Reads c4_required_items from the Work Order
    2. Calculates balance quantities (required - already picked)
    3. Creates a Pick List with balance quantities
    
    Args:
        work_order_id: Name of the Work Order
        
    Returns:
        Pick List document as dict
    """
    wo = frappe.get_doc("Work Order", work_order_id)
    
    if not wo.c4_required_items:
        frappe.throw(_("No required items found in Work Order {0}").format(work_order_id))
    
    # Get already picked quantities from existing Pick Lists
    picked_quantities = _get_picked_quantities(work_order_id)
    
    # Create Pick List
    pick_list = frappe.new_doc("Pick List")
    pick_list.purpose = "Material Transfer for Manufacture"
    pick_list.work_order = work_order_id
    pick_list.c4_work_order = work_order_id
    pick_list.company = wo.company
    pick_list.c4_status = "Open"
    
    # Add items with balance quantities
    items_added = False
    for wo_item in wo.c4_required_items:
        item_code = wo_item.item_code
        required_qty = flt(wo_item.required_qty)
        
        # Get already picked quantity for this item
        already_picked = picked_quantities.get(item_code, 0.0)
        
        # Calculate balance
        balance_qty = required_qty - already_picked
        
        if balance_qty > 0:
            # Add to Pick List
            pick_list.append("locations", {
                "item_code": item_code,
                "qty": balance_qty,
                "stock_qty": balance_qty,
                "uom": wo_item.stock_uom,
                "stock_uom": wo_item.stock_uom,
                "conversion_factor": 1.0,
                "warehouse": wo_item.source_warehouse or wo.source_warehouse,
                "c4_wo_required_qty": required_qty,
                "c4_balance_qty": balance_qty,
                "c4_consumed_qty": 0.0,
            })
            items_added = True
    
    if not items_added:
        frappe.throw(_("No balance quantity to pick for Work Order {0}. All items have been picked.").format(work_order_id))
    
    # Set missing values
    pick_list.set_item_locations()
    
    return pick_list.as_dict()


def _get_picked_quantities(work_order_id):
    """
    Get total picked quantities for each item from submitted Pick Lists
    linked to this Work Order.
    
    Returns:
        dict: {item_code: total_picked_qty}
    """
    # Get all submitted Pick Lists for this Work Order
    pick_lists = frappe.get_all(
        "Pick List",
        filters={
            "c4_work_order": work_order_id,
            "docstatus": 1
        },
        pluck="name"
    )
    
    if not pick_lists:
        return {}
    
    # Get all items from these Pick Lists
    pick_list_items = frappe.get_all(
        "Pick List Item",
        filters={
            "parent": ["in", pick_lists]
        },
        fields=["item_code", "qty", "picked_qty"]
    )
    
    # Aggregate by item_code
    picked_quantities = {}
    for item in pick_list_items:
        item_code = item.item_code
        # Use picked_qty if available, otherwise use qty
        qty = flt(item.get("picked_qty") or item.get("qty") or 0.0)
        
        if item_code in picked_quantities:
            picked_quantities[item_code] += qty
        else:
            picked_quantities[item_code] = qty
    
    return picked_quantities


@frappe.whitelist()
def get_work_order_balance(work_order_id):
    """
    Get balance information for a Work Order.
    
    Returns summary of:
    - Required quantities
    - Picked quantities
    - Balance quantities
    
    Args:
        work_order_id: Name of the Work Order
        
    Returns:
        dict with balance information
    """
    wo = frappe.get_doc("Work Order", work_order_id)
    
    if not wo.c4_required_items:
        return {
            "items": [],
            "total_required": 0.0,
            "total_picked": 0.0,
            "total_balance": 0.0
        }
    
    picked_quantities = _get_picked_quantities(work_order_id)
    
    items = []
    total_required = 0.0
    total_picked = 0.0
    total_balance = 0.0
    
    for wo_item in wo.c4_required_items:
        item_code = wo_item.item_code
        required_qty = flt(wo_item.required_qty)
        picked_qty = picked_quantities.get(item_code, 0.0)
        balance_qty = required_qty - picked_qty
        
        items.append({
            "item_code": item_code,
            "item_name": wo_item.item_name,
            "required_qty": required_qty,
            "picked_qty": picked_qty,
            "balance_qty": balance_qty,
            "stock_uom": wo_item.stock_uom,
            "source_warehouse": wo_item.source_warehouse
        })
        
        total_required += required_qty
        total_picked += picked_qty
        total_balance += balance_qty
    
    return {
        "items": items,
        "total_required": total_required,
        "total_picked": total_picked,
        "total_balance": total_balance
    }
