import frappe
from c4factory.c4_manufacturing import work_order_hooks


def set_wip_target_warehouse(doc, method=None):
    """
    Hook on Stock Entry validate.

    For Stock Entry of type 'Material Transfer for Manufacture' linked to a Work Order:
      - Ensure each item row's t_warehouse is set to the Work Order WIP Warehouse
        if it is empty.

    For Stock Entry of type 'Manufacture' linked to a Work Order:
      - Ensure fg_completed_qty / manufactured_qty / for_quantity are set
        from the Finished Good row qty, so the "Manufactured Qty" mandatory
        validation passes in v15.
    """

    # Step 2 logic: Material Transfer for Manufacture → target WIP warehouse
    if doc.stock_entry_type == "Material Transfer for Manufacture" and getattr(doc, "work_order", None):
        _ensure_wip_target_warehouse(doc)

    # Manufacture entries → ensure manufactured qty header fields
    if doc.stock_entry_type == "Manufacture" and getattr(doc, "work_order", None):
        _ensure_fg_qty_fields_from_finished_item(doc)


def on_submit_update_work_order_costing(doc, method=None):
    """
    Hook on Stock Entry on_submit.

    Whenever a Material Transfer for Manufacture (or Manufacture) Stock Entry
    linked to a Work Order is submitted, recompute the Work Order costing
    (raw + operating + scrap + total).

    Raw Material Cost itself only uses Material Transfer entries (see
    _get_raw_material_cost_from_material_transfers), so calling this on
    Manufacture won't double count.
    
    Also updates Pick List consumed quantities if linked.
    """
    if not getattr(doc, "work_order", None):
        return

    if doc.stock_entry_type not in ("Material Transfer for Manufacture", "Manufacture"):
        return

    # Update Work Order costing
    work_order_hooks.recalculate_costing_for_work_order(doc.work_order)
    
    # Update Pick List consumed quantities if linked
    if getattr(doc, "c4_pick_list", None):
        update_pick_list_consumed_qty(doc)


def on_cancel_update_pick_list(doc, method=None):
    """
    Hook on Stock Entry on_cancel.
    
    When a Stock Entry linked to a Pick List is cancelled,
    recalculate the Pick List balance.
    """
    if getattr(doc, "c4_pick_list", None):
        # Import here to avoid circular dependency
        from c4factory.c4_manufacturing import pick_list_hooks
        pick_list_hooks.recalculate_pick_list_balance(doc.c4_pick_list)
        
        # Also update Work Order if linked
        if getattr(doc, "work_order", None):
            work_order_hooks.recalculate_costing_for_work_order(doc.work_order)


def update_pick_list_consumed_qty(stock_entry_doc):
    """
    Update consumed quantities in Pick List when Stock Entry is submitted.
    
    This function:
    1. Gets all items from Stock Entry that are being consumed (have s_warehouse)
    2. Updates corresponding Pick List items with consumed quantities
    3. Recalculates Pick List balance and status
    """
    if not stock_entry_doc.c4_pick_list:
        return
    
    try:
        # Import here to avoid circular dependency
        from c4factory.c4_manufacturing import pick_list_hooks
        
        # Get Pick List
        pick_list = frappe.get_doc("Pick List", stock_entry_doc.c4_pick_list)
        
        # Aggregate consumed quantities by item from Stock Entry
        consumed_by_item = {}
        for se_item in stock_entry_doc.get("items") or []:
            # Only count items being consumed (have source warehouse)
            if se_item.s_warehouse:
                item_code = se_item.item_code
                qty = float(se_item.qty or 0.0)
                
                if item_code in consumed_by_item:
                    consumed_by_item[item_code] += qty
                else:
                    consumed_by_item[item_code] = qty
        
        # Update Pick List items
        updated = False
        for pl_item in pick_list.get("locations") or []:
            if pl_item.item_code in consumed_by_item:
                # Add to consumed quantity
                current_consumed = float(pl_item.get("c4_consumed_qty") or 0.0)
                pl_item.c4_consumed_qty = current_consumed + consumed_by_item[pl_item.item_code]
                
                # Recalculate balance
                pl_item.c4_balance_qty = float(pl_item.qty or 0.0) - pl_item.c4_consumed_qty
                updated = True
        
        if updated:
            # Recalculate totals and status
            pick_list_hooks.calculate_totals(pick_list)
            pick_list_hooks.update_pick_list_status(pick_list)
            
            # Save Pick List
            pick_list.flags.ignore_validate_update_after_submit = True
            pick_list.flags.ignore_permissions = True
            pick_list.save()
            
            frappe.db.commit()
            
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title=f"Error updating Pick List {stock_entry_doc.c4_pick_list} from Stock Entry {stock_entry_doc.name}"
        )


def _ensure_wip_target_warehouse(doc):
    """Set t_warehouse from Work Order WIP for transfer SE if missing."""
    wip_warehouse = frappe.db.get_value("Work Order", doc.work_order, "wip_warehouse")
    if not wip_warehouse:
        return

    for row in doc.get("items", []):
        if not row.t_warehouse:
            row.t_warehouse = wip_warehouse


def _ensure_fg_qty_fields_from_finished_item(doc):
    """
    For Manufacture Stock Entry:

    - Find the Finished Good row (is_finished_item or target = WO.fg_warehouse).
    - Use its qty as the "manufactured quantity".
    - Set header fields:
        fg_completed_qty
        manufactured_qty (if exists)
        for_quantity (if exists)
    so ERPNext's "Manufactured Qty is mandatory" validation is satisfied.
    """

    if not doc.items:
        return

    # Get the Work Order FG warehouse to help identify the FG row
    fg_warehouse = frappe.db.get_value("Work Order", doc.work_order, "fg_warehouse")

    finished_qty = 0.0

    for row in doc.items:
        # Prefer explicit finished item flag
        if getattr(row, "is_finished_item", None):
            finished_qty = row.qty or 0.0
            break

    # If no explicit finished row flag, fall back to row with t_warehouse = fg_warehouse and no s_warehouse
    if not finished_qty and fg_warehouse:
        for row in doc.items:
            if row.t_warehouse == fg_warehouse and not row.s_warehouse:
                finished_qty = row.qty or 0.0
                break

    if not finished_qty:
        # Nothing to set; let standard validations handle it if needed
        return

    # Set header "manufactured quantity" style fields
    doc.fg_completed_qty = finished_qty

    # Some ERPNext versions use these additional fields; set them if present
    if hasattr(doc, "manufactured_qty"):
        doc.manufactured_qty = finished_qty

    if hasattr(doc, "for_quantity"):
        doc.for_quantity = finished_qty
