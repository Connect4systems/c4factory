import frappe


def copy_scrap_from_bom(doc, method=None):
    """
    When a new Work Order is created from a BOM, copy BOM.scrap_items
    into Work Order.c4_scrap_items (child table type: BOM Scrap Item).

    - Runs only if:
      * doc.bom_no is set
      * c4_scrap_items is empty
    - After copying, item_name / stock_uom / rate are ensured from Item master.
    """
    if not getattr(doc, "bom_no", None):
        return

    # if there are already scrap rows, do nothing
    if getattr(doc, "c4_scrap_items", None):
        if len(doc.c4_scrap_items):
            return

    bom = frappe.get_doc("BOM", doc.bom_no)

    # copy BOM Scrap Items rows
    for row in bom.scrap_items:
        # BOM Scrap Item uses 'stock_qty' as quantity field
        new_row = doc.append("c4_scrap_items", {
            "item_code": row.item_code,
            "item_name": row.item_name,
            # stock_uom will be overridden by _ensure_scrap_item_fields_from_item
            "stock_uom": row.stock_uom,
            "stock_qty": row.stock_qty,
            "rate": row.rate,
            "amount": row.amount,
        })

        # ensure fields from Item master (including overriding stock_uom)
        _ensure_scrap_item_fields_from_item(new_row)


def copy_required_items_from_bom(doc, method=None):
    """
    When a new Work Order is created from a BOM, copy BOM.items
    into Work Order.c4_required_items (child table type: Work Order Item).

    This allows users to edit required items before submission.
    
    - Runs only if:
      * doc.bom_no is set
      * c4_required_items is empty
    """
    if not getattr(doc, "bom_no", None):
        return

    # if there are already required item rows, do nothing
    if getattr(doc, "c4_required_items", None):
        if len(doc.c4_required_items):
            return

    bom = frappe.get_doc("BOM", doc.bom_no)
    
    # Calculate the multiplier based on work order qty vs BOM qty
    multiplier = (doc.qty or 1.0) / (bom.quantity or 1.0)

    # copy BOM Items to c4_required_items
    for bom_item in bom.items:
        required_qty = (bom_item.qty or 0.0) * multiplier
        
        new_row = doc.append("c4_required_items", {
            "item_code": bom_item.item_code,
            "item_name": bom_item.item_name,
            "description": bom_item.description,
            "source_warehouse": bom_item.source_warehouse or doc.source_warehouse,
            "required_qty": required_qty,
            "transferred_qty": 0.0,
            "consumed_qty": 0.0,
            "returned_qty": 0.0,
            "available_qty_at_source_warehouse": 0.0,
            "available_qty_at_wip_warehouse": 0.0,
        })
        
        # Get item details
        item = frappe.get_cached_value(
            "Item", 
            bom_item.item_code, 
            ["stock_uom", "item_name", "description"], 
            as_dict=True
        )
        
        if item:
            new_row.stock_uom = item.stock_uom
            if not new_row.item_name:
                new_row.item_name = item.item_name
            if not new_row.description:
                new_row.description = item.description


def _ensure_scrap_item_fields_from_item(row):
    """
    Helper: for a BOM Scrap Item row, make sure:
    - item_name
    - stock_uom (ALWAYS from Item default)
    - rate (from Item valuation if missing/zero)

    Rate is taken from Item.valuation_rate (fallback last_purchase_rate).
    """
    if not row.item_code:
        return

    fields = ["item_name", "stock_uom", "valuation_rate", "last_purchase_rate"]
    item = frappe.get_cached_value("Item", row.item_code, fields, as_dict=True)

    # Always override stock_uom by Item default
    row.stock_uom = item.stock_uom

    # Fill item_name if missing
    if not getattr(row, "item_name", None):
        row.item_name = item.item_name

    # If rate is zero/None, take a valuation from Item
    if not row.rate:
        rate = item.valuation_rate or item.last_purchase_rate or 0.0
        row.rate = float(rate)


def update_scrap_and_costing(doc, method=None):
    """
    On every save/validate of Work Order:

    - Ensure each scrap row has item_name / stock_uom / rate (from Item if needed)
    - Ensure each scrap row has amount = stock_qty * rate
    - Compute:
        c4_scrap_material_cost  = sum(scrap.amount)
        c4_raw_material_cost    = value of Material Transfers to WIP (actual SE)
        c4_operating_cost       = from WO operations
        c4_total_cost           = raw + operating - scrap
    """

    # --- 1) Scrap rows + Scrap Material Cost ---
    total_scrap_amount = 0.0

    for row in (doc.get("c4_scrap_items") or []):
        # Ensure fields come from Item master (overrides stock_uom)
        _ensure_scrap_item_fields_from_item(row)

        # In BOM Scrap Item, quantity fieldname is 'stock_qty'
        qty = row.get("stock_qty") or 0.0
        rate = row.rate or 0.0

        row.amount = float(qty) * float(rate)
        total_scrap_amount += (row.amount or 0.0)

    doc.c4_scrap_material_cost = total_scrap_amount

    # --- 2) Raw Material Cost from Material Transfer to WIP ---
    raw_material_cost = _get_raw_material_cost_from_material_transfers(doc.name, doc.wip_warehouse)
    doc.c4_raw_material_cost = raw_material_cost

    # --- 3) Operating Cost from WO fields ---
    operating_cost = 0.0
    if doc.actual_operating_cost:
        operating_cost = float(doc.actual_operating_cost)
    elif doc.total_operating_cost:
        operating_cost = float(doc.total_operating_cost)

    doc.c4_operating_cost = operating_cost

    # --- 4) Total Cost = Raw + Operating - Scrap ---
    raw = doc.c4_raw_material_cost or 0.0
    op = doc.c4_operating_cost or 0.0
    scrap = doc.c4_scrap_material_cost or 0.0

    doc.c4_total_cost = float(raw) + float(op) - float(scrap)


def _get_raw_material_cost_from_material_transfers(work_order_name, wip_warehouse):
    """
    Sum value of materials TRANSFERRED INTO WIP for this WO.

    We consider all Stock Entry Detail rows where:
    - parent is a submitted Stock Entry
    - stock_entry_type = 'Material Transfer for Manufacture'
    - work_order = work_order_name
    - t_warehouse = wip_warehouse   (i.e., moved into WIP)

    We look at basic_amount / amount.
    """

    if not work_order_name or not wip_warehouse:
        return 0.0

    se_names = frappe.get_all(
        "Stock Entry",
        filters={
            "work_order": work_order_name,
            "docstatus": 1,
            "stock_entry_type": "Material Transfer for Manufacture",
        },
        pluck="name",
    )

    if not se_names:
        return 0.0

    rows = frappe.get_all(
        "Stock Entry Detail",
        filters={
            "parent": ["in", se_names],
            "t_warehouse": wip_warehouse,
        },
        fields=["basic_amount", "amount"],
    )

    total = 0.0
    for r in rows:
        value = r.get("basic_amount") or r.get("amount") or 0.0
        total += float(value)

    return total


def calculate_required_items_balance(doc, method=None):
    """
    Calculate balance quantities for c4_required_items based on:
    - Pick Lists created from this Work Order
    - Stock Entries linked to Pick Lists
    
    Updates:
    - c4_total_picked_qty: Total quantity picked across all Pick Lists
    - c4_total_consumed_qty: Total quantity consumed in Stock Entries
    """
    if not doc.name:
        return
    
    # Get all Pick Lists for this Work Order
    pick_lists = frappe.get_all(
        "Pick List",
        filters={
            "c4_work_order": doc.name,
            "docstatus": 1
        },
        pluck="name"
    )
    
    total_picked = 0.0
    total_consumed = 0.0
    
    if pick_lists:
        # Get picked quantities from Pick List Items
        picked_items = frappe.get_all(
            "Pick List Item",
            filters={
                "parent": ["in", pick_lists]
            },
            fields=["item_code", "qty", "picked_qty"]
        )
        
        for item in picked_items:
            total_picked += float(item.get("picked_qty") or item.get("qty") or 0.0)
        
        # Get consumed quantities from Stock Entries linked to Pick Lists
        stock_entries = frappe.get_all(
            "Stock Entry",
            filters={
                "c4_pick_list": ["in", pick_lists],
                "docstatus": 1,
                "stock_entry_type": ["in", ["Material Transfer for Manufacture", "Manufacture"]]
            },
            pluck="name"
        )
        
        if stock_entries:
            consumed_items = frappe.get_all(
                "Stock Entry Detail",
                filters={
                    "parent": ["in", stock_entries],
                    "s_warehouse": ["is", "set"]  # Items being consumed (have source warehouse)
                },
                fields=["qty"]
            )
            
            for item in consumed_items:
                total_consumed += float(item.get("qty") or 0.0)
    
    doc.c4_total_picked_qty = total_picked
    doc.c4_total_consumed_qty = total_consumed


def recalculate_costing_for_work_order(work_order_name):
    """
    Utility: load a Work Order, recompute costing, and save it.

    Used from Stock Entry hooks when a Material Transfer to WIP is submitted.
    """
    if not work_order_name:
        return

    wo = frappe.get_doc("Work Order", work_order_name)
    # Run the same logic used on validate
    update_scrap_and_costing(wo)
    calculate_required_items_balance(wo)

    # We might be saving a submitted WO; ignore update-after-submit warnings
    wo.flags.ignore_validate_update_after_submit = True
    wo.flags.ignore_permissions = True
    wo.save()
