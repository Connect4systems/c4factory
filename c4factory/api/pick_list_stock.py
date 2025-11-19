import frappe
from frappe import _
from frappe.utils import flt, cstr


@frappe.whitelist()
def make_stock_entry(pick_list_id, purpose="Material Transfer for Manufacture"):
    """
    Create a Stock Entry from a Pick List.
    
    This function creates Stock Entry based on Pick List items (not BOM).
    Supports partial stock entries based on balance quantities.
    
    Args:
        pick_list_id: Name of the Pick List
        purpose: Stock Entry purpose (default: Material Transfer for Manufacture)
        
    Returns:
        Stock Entry document as dict
    """
    pick_list = frappe.get_doc("Pick List", pick_list_id)
    
    if not pick_list.c4_work_order:
        frappe.throw(_("Pick List {0} is not linked to a Work Order").format(pick_list_id))
    
    wo = frappe.get_doc("Work Order", pick_list.c4_work_order)
    
    # Create Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.purpose = purpose
    se.stock_entry_type = purpose
    se.company = pick_list.company or wo.company
    se.work_order = wo.name
    se.c4_pick_list = pick_list_id
    se.from_bom = 0  # Important: do NOT pull from BOM
    
    if purpose == "Material Transfer for Manufacture":
        # Transfer materials from source to WIP warehouse
        if not wo.wip_warehouse:
            frappe.throw(_("Work Order {0} has no WIP Warehouse set").format(wo.name))
        
        for item in pick_list.get("locations") or []:
            # Only add items with balance quantity
            balance_qty = flt(item.get("c4_balance_qty") or 0.0)
            if balance_qty <= 0:
                continue
            
            se.append("items", {
                "item_code": item.item_code,
                "qty": balance_qty,
                "uom": item.uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": item.conversion_factor or 1.0,
                "s_warehouse": item.warehouse,
                "t_warehouse": wo.wip_warehouse,
                "is_finished_item": 0,
                "is_scrap_item": 0,
            })
    
    elif purpose == "Manufacture":
        # Manufacture: consume from WIP, create finished goods and scrap
        if not wo.wip_warehouse:
            frappe.throw(_("Work Order {0} has no WIP Warehouse set").format(wo.name))
        
        if not wo.fg_warehouse:
            frappe.throw(_("Work Order {0} has no Finished Goods Warehouse set").format(wo.name))
        
        # Calculate FG quantity based on remaining to manufacture
        fg_qty = (wo.qty or 0) - (wo.produced_qty or 0)
        if fg_qty <= 0:
            frappe.throw(_("No remaining quantity to manufacture for Work Order {0}").format(wo.name))
        
        # 1) RAW MATERIALS - consume from WIP
        for item in pick_list.get("locations") or []:
            # Use balance quantity (not yet consumed)
            balance_qty = flt(item.get("c4_balance_qty") or 0.0)
            if balance_qty <= 0:
                continue
            
            se.append("items", {
                "item_code": item.item_code,
                "qty": balance_qty,
                "uom": item.uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": item.conversion_factor or 1.0,
                "s_warehouse": wo.wip_warehouse,
                "t_warehouse": None,
                "is_finished_item": 0,
                "is_scrap_item": 0,
            })
        
        # 2) SCRAP ITEMS - create in scrap warehouse
        if wo.scrap_warehouse and wo.get("c4_scrap_items"):
            for scrap_item in wo.c4_scrap_items:
                scrap_qty = flt(scrap_item.get("stock_qty") or 0.0)
                if scrap_qty <= 0:
                    continue
                
                se.append("items", {
                    "item_code": scrap_item.item_code,
                    "qty": scrap_qty,
                    "uom": scrap_item.stock_uom,
                    "stock_uom": scrap_item.stock_uom,
                    "conversion_factor": 1.0,
                    "s_warehouse": None,
                    "t_warehouse": wo.scrap_warehouse,
                    "is_finished_item": 0,
                    "is_scrap_item": 1,
                })
        
        # 3) FINISHED GOOD - create in FG warehouse
        se.append("items", {
            "item_code": wo.production_item,
            "qty": fg_qty,
            "uom": wo.stock_uom,
            "stock_uom": wo.stock_uom,
            "conversion_factor": 1.0,
            "s_warehouse": None,
            "t_warehouse": wo.fg_warehouse,
            "is_finished_item": 1,
            "is_scrap_item": 0,
        })
        
        # Set manufactured qty fields
        se.fg_completed_qty = fg_qty
        if hasattr(se, "manufactured_qty"):
            se.manufactured_qty = fg_qty
        if hasattr(se, "for_quantity"):
            se.for_quantity = fg_qty
    
    else:
        frappe.throw(_("Unsupported Stock Entry purpose: {0}").format(purpose))
    
    # Set missing values (rates, amounts, etc.)
    se.set_missing_values()
    
    return se.as_dict()


@frappe.whitelist()
def make_partial_stock_entry(pick_list_id, items_json, purpose="Material Transfer for Manufacture"):
    """
    Create a partial Stock Entry from Pick List with custom quantities.
    
    Args:
        pick_list_id: Name of the Pick List
        items_json: JSON string of items with quantities: [{"item_code": "...", "qty": ...}, ...]
        purpose: Stock Entry purpose
        
    Returns:
        Stock Entry document as dict
    """
    import json
    
    pick_list = frappe.get_doc("Pick List", pick_list_id)
    
    if not pick_list.c4_work_order:
        frappe.throw(_("Pick List {0} is not linked to a Work Order").format(pick_list_id))
    
    wo = frappe.get_doc("Work Order", pick_list.c4_work_order)
    
    # Parse items JSON
    try:
        items_to_transfer = json.loads(items_json)
    except Exception:
        frappe.throw(_("Invalid items JSON format"))
    
    if not items_to_transfer:
        frappe.throw(_("No items specified for Stock Entry"))
    
    # Create Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.purpose = purpose
    se.stock_entry_type = purpose
    se.company = pick_list.company or wo.company
    se.work_order = wo.name
    se.c4_pick_list = pick_list_id
    se.from_bom = 0
    
    # Create a map of item_code to requested qty
    qty_map = {item["item_code"]: flt(item["qty"]) for item in items_to_transfer}
    
    if purpose == "Material Transfer for Manufacture":
        if not wo.wip_warehouse:
            frappe.throw(_("Work Order {0} has no WIP Warehouse set").format(wo.name))
        
        for item in pick_list.get("locations") or []:
            if item.item_code not in qty_map:
                continue
            
            requested_qty = qty_map[item.item_code]
            balance_qty = flt(item.get("c4_balance_qty") or 0.0)
            
            # Use minimum of requested and balance
            qty_to_transfer = min(requested_qty, balance_qty)
            
            if qty_to_transfer <= 0:
                continue
            
            se.append("items", {
                "item_code": item.item_code,
                "qty": qty_to_transfer,
                "uom": item.uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": item.conversion_factor or 1.0,
                "s_warehouse": item.warehouse,
                "t_warehouse": wo.wip_warehouse,
                "is_finished_item": 0,
                "is_scrap_item": 0,
            })
    
    elif purpose == "Manufacture":
        # For Manufacture, use the specified quantities
        if not wo.wip_warehouse or not wo.fg_warehouse:
            frappe.throw(_("Work Order {0} missing WIP or FG Warehouse").format(wo.name))
        
        # Calculate FG qty (could be partial)
        fg_qty = flt(items_to_transfer[0].get("fg_qty", 0)) if items_to_transfer else 0
        if fg_qty <= 0:
            fg_qty = (wo.qty or 0) - (wo.produced_qty or 0)
        
        # Raw materials
        for item in pick_list.get("locations") or []:
            if item.item_code not in qty_map:
                continue
            
            qty = qty_map[item.item_code]
            if qty <= 0:
                continue
            
            se.append("items", {
                "item_code": item.item_code,
                "qty": qty,
                "uom": item.uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": item.conversion_factor or 1.0,
                "s_warehouse": wo.wip_warehouse,
                "t_warehouse": None,
                "is_finished_item": 0,
                "is_scrap_item": 0,
            })
        
        # Scrap items (if any)
        if wo.scrap_warehouse and wo.get("c4_scrap_items"):
            for scrap_item in wo.c4_scrap_items:
                scrap_qty = flt(scrap_item.get("stock_qty") or 0.0)
                if scrap_qty > 0:
                    se.append("items", {
                        "item_code": scrap_item.item_code,
                        "qty": scrap_qty,
                        "uom": scrap_item.stock_uom,
                        "stock_uom": scrap_item.stock_uom,
                        "conversion_factor": 1.0,
                        "s_warehouse": None,
                        "t_warehouse": wo.scrap_warehouse,
                        "is_finished_item": 0,
                        "is_scrap_item": 1,
                    })
        
        # Finished good
        se.append("items", {
            "item_code": wo.production_item,
            "qty": fg_qty,
            "uom": wo.stock_uom,
            "stock_uom": wo.stock_uom,
            "conversion_factor": 1.0,
            "s_warehouse": None,
            "t_warehouse": wo.fg_warehouse,
            "is_finished_item": 1,
            "is_scrap_item": 0,
        })
        
        se.fg_completed_qty = fg_qty
        if hasattr(se, "manufactured_qty"):
            se.manufactured_qty = fg_qty
        if hasattr(se, "for_quantity"):
            se.for_quantity = fg_qty
    
    se.set_missing_values()
    
    return se.as_dict()
