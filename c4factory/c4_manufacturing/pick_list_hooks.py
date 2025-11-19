import frappe
from frappe import _


def validate_pick_list(doc, method=None):
    """
    On Pick List validate:
    - Calculate balance quantities for each item
    - Calculate total quantities
    - Update Pick List status based on balance
    """
    calculate_item_balances(doc)
    calculate_totals(doc)
    update_pick_list_status(doc)


def calculate_item_balances(doc):
    """
    For each Pick List Item, calculate:
    - c4_balance_qty = qty - c4_consumed_qty
    
    c4_consumed_qty is updated when Stock Entries are submitted.
    """
    for item in doc.get("locations") or []:
        qty = float(item.qty or 0.0)
        consumed = float(item.get("c4_consumed_qty") or 0.0)
        
        # Balance = Picked Qty - Consumed Qty
        item.c4_balance_qty = qty - consumed


def calculate_totals(doc):
    """
    Calculate Pick List header totals:
    - c4_total_qty: Sum of all item quantities
    - c4_consumed_qty: Sum of all consumed quantities
    - c4_balance_qty: Total - Consumed
    """
    total_qty = 0.0
    consumed_qty = 0.0
    
    for item in doc.get("locations") or []:
        total_qty += float(item.qty or 0.0)
        consumed_qty += float(item.get("c4_consumed_qty") or 0.0)
    
    doc.c4_total_qty = total_qty
    doc.c4_consumed_qty = consumed_qty
    doc.c4_balance_qty = total_qty - consumed_qty


def update_pick_list_status(doc):
    """
    Update Pick List status based on balance:
    - Completed: if c4_balance_qty <= 0
    - Open: otherwise
    """
    if doc.c4_balance_qty <= 0:
        doc.c4_status = "Completed"
    else:
        doc.c4_status = "Open"


def on_submit_update_work_order(doc, method=None):
    """
    When Pick List is submitted, update the linked Work Order
    to recalculate picked quantities.
    """
    if not doc.c4_work_order:
        return
    
    try:
        # Import here to avoid circular dependency
        from c4factory.c4_manufacturing import work_order_hooks
        work_order_hooks.recalculate_costing_for_work_order(doc.c4_work_order)
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title=f"Error updating Work Order {doc.c4_work_order} from Pick List {doc.name}"
        )


def on_cancel_update_work_order(doc, method=None):
    """
    When Pick List is cancelled, update the linked Work Order
    to recalculate picked quantities.
    """
    if not doc.c4_work_order:
        return
    
    try:
        # Import here to avoid circular dependency
        from c4factory.c4_manufacturing import work_order_hooks
        work_order_hooks.recalculate_costing_for_work_order(doc.c4_work_order)
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title=f"Error updating Work Order {doc.c4_work_order} from Pick List {doc.name}"
        )


def update_consumed_qty_from_stock_entry(pick_list_name, item_code, consumed_qty):
    """
    Update consumed quantity for a specific item in Pick List.
    Called from Stock Entry hooks when a Stock Entry is submitted.
    
    Args:
        pick_list_name: Name of the Pick List
        item_code: Item code to update
        consumed_qty: Quantity consumed in Stock Entry
    """
    if not pick_list_name:
        return
    
    try:
        pick_list = frappe.get_doc("Pick List", pick_list_name)
        
        # Find matching item in Pick List
        for item in pick_list.get("locations") or []:
            if item.item_code == item_code:
                # Add to consumed quantity
                current_consumed = float(item.get("c4_consumed_qty") or 0.0)
                item.c4_consumed_qty = current_consumed + float(consumed_qty)
                
                # Recalculate balance
                item.c4_balance_qty = float(item.qty or 0.0) - item.c4_consumed_qty
                break
        
        # Recalculate totals and status
        calculate_totals(pick_list)
        update_pick_list_status(pick_list)
        
        # Save with flags to avoid validation issues
        pick_list.flags.ignore_validate_update_after_submit = True
        pick_list.flags.ignore_permissions = True
        pick_list.save()
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title=f"Error updating Pick List {pick_list_name} consumed qty"
        )


def recalculate_pick_list_balance(pick_list_name):
    """
    Utility function to recalculate Pick List balance and status.
    Can be called from anywhere to refresh Pick List state.
    """
    if not pick_list_name:
        return
    
    try:
        pick_list = frappe.get_doc("Pick List", pick_list_name)
        
        # Recalculate from Stock Entries
        stock_entries = frappe.get_all(
            "Stock Entry",
            filters={
                "c4_pick_list": pick_list_name,
                "docstatus": 1
            },
            pluck="name"
        )
        
        if stock_entries:
            # Reset consumed quantities
            for item in pick_list.get("locations") or []:
                item.c4_consumed_qty = 0.0
            
            # Recalculate from Stock Entry Details
            se_items = frappe.get_all(
                "Stock Entry Detail",
                filters={
                    "parent": ["in", stock_entries],
                    "s_warehouse": ["is", "set"]  # Items being consumed
                },
                fields=["item_code", "qty"]
            )
            
            # Aggregate consumed quantities by item
            consumed_by_item = {}
            for se_item in se_items:
                item_code = se_item.item_code
                qty = float(se_item.qty or 0.0)
                consumed_by_item[item_code] = consumed_by_item.get(item_code, 0.0) + qty
            
            # Update Pick List items
            for item in pick_list.get("locations") or []:
                if item.item_code in consumed_by_item:
                    item.c4_consumed_qty = consumed_by_item[item.item_code]
                    item.c4_balance_qty = float(item.qty or 0.0) - item.c4_consumed_qty
        
        # Recalculate totals and status
        calculate_totals(pick_list)
        update_pick_list_status(pick_list)
        
        # Save
        pick_list.flags.ignore_validate_update_after_submit = True
        pick_list.flags.ignore_permissions = True
        pick_list.save()
        
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title=f"Error recalculating Pick List {pick_list_name} balance"
        )
