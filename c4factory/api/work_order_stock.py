import frappe
from erpnext.manufacturing.doctype.work_order.work_order import (
    make_stock_entry as erpnext_make_stock_entry,
)


@frappe.whitelist()
def make_stock_entry(work_order_id, purpose, qty=None):
    """
    Override for erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry

    - For purpose != "Manufacture": delegate to standard ERPNext behavior.
    - For purpose == "Manufacture": build Stock Entry from:
        * ACTUAL transfers to WIP (Material Transfer for Manufacture), and
        * Scrap items defined on the Work Order (c4_scrap_items).

    Final behavior:
    - Raw material rows:
        s_warehouse = WIP Warehouse
        t_warehouse = (empty)
    - Scrap rows:
        s_warehouse = (empty)
        t_warehouse = Scrap Warehouse
    - Finished good row:
        s_warehouse = (empty)
        t_warehouse = FG Warehouse
    """
    if purpose != "Manufacture":
        # For Material Transfer, Disassemble, etc: use standard logic
        return erpnext_make_stock_entry(work_order_id, purpose, qty)

    # Custom logic for Manufacture
    wo = frappe.get_doc("Work Order", work_order_id)

    if not wo.wip_warehouse:
        frappe.throw(f"Work Order {wo.name} has no WIP Warehouse set.")

    if not wo.fg_warehouse:
        frappe.throw(f"Work Order {wo.name} has no Finished Goods Warehouse set.")

    # Determine FG quantity
    if qty:
        try:
            fg_qty = float(qty)
        except Exception:
            fg_qty = frappe.utils.flt(qty)
    else:
        # standard behavior: remaining to produce
        fg_qty = (wo.qty or 0) - (wo.produced_qty or 0)

    if fg_qty <= 0:
        frappe.throw(
            f"No remaining quantity to manufacture for Work Order {wo.name}."
        )

    # Collect ACTUAL transfers to WIP for this WO
    transferred_items = _get_transferred_items_to_wip(wo.name, wo.wip_warehouse)

    if not transferred_items:
        frappe.throw(
            "No submitted 'Material Transfer for Manufacture' Stock Entries found "
            f"for Work Order {wo.name}. Please transfer materials to WIP before finishing."
        )

    # --------------------------------------------------------------------
    # Create Manufacture Stock Entry (header)
    # --------------------------------------------------------------------
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Manufacture"
    se.stock_entry_type = "Manufacture"
    se.company = wo.company
    se.work_order = wo.name
    se.from_bom = 0  # do NOT pull from BOM
    se.use_multi_level_bom = wo.use_multi_level_bom

    # v15: set all manufactured-qty style fields
    se.fg_completed_qty = fg_qty
    if hasattr(se, "manufactured_qty"):
        se.manufactured_qty = fg_qty
    if hasattr(se, "for_quantity"):
        se.for_quantity = fg_qty

    # We'll mark rows with a small flag so we can enforce warehouses AFTER
    # set_missing_values() (because ERPNext may override them).

    # 1) RAW MATERIAL ROWS – consumed from WIP
    for item in transferred_items:
        row = se.append("items", {
            "item_code": item["item_code"],
            "qty": item["qty"],
            "uom": item["stock_uom"],
            "stock_uom": item["stock_uom"],
            "conversion_factor": 1,
            "is_finished_item": 0,
            "is_scrap_item": 0,
        })
        row._c4_role = "raw"

    # 2) SCRAP ITEMS ROWS – created in Scrap Warehouse
    if wo.scrap_warehouse:
        for row in (wo.get("c4_scrap_items") or []):
            qty = (row.get("stock_qty") or 0.0)
            if qty <= 0:
                continue

            scrap_row = se.append("items", {
                "item_code": row.item_code,
                "qty": qty,
                "uom": row.stock_uom,
                "stock_uom": row.stock_uom,
                "conversion_factor": 1,
                "is_scrap_item": 1,
                "is_finished_item": 0,
            })
            scrap_row._c4_role = "scrap"

    # 3) FINISHED GOOD ROW – into FG warehouse
    fg_row = se.append("items", {
        "item_code": wo.production_item,
        "qty": fg_qty,
        "uom": wo.stock_uom,
        "stock_uom": wo.stock_uom,
        "conversion_factor": 1,
        "is_finished_item": 1,
        "is_scrap_item": 0,
    })
    fg_row._c4_role = "fg"

    # Let ERPNext fill valuation etc.
    se.set_missing_values()

    # ENFORCE WAREHOUSES AFTER set_missing_values
    for row in se.items:
        role = getattr(row, "_c4_role", None)

        if role == "raw":
            # raw materials: consumed from WIP
            row.s_warehouse = wo.wip_warehouse
            row.t_warehouse = None

        elif role == "scrap":
            # scrap: created in scrap warehouse, no source
            row.s_warehouse = None
            row.t_warehouse = wo.scrap_warehouse

        elif role == "fg":
            # finished good: created in FG warehouse, no source
            row.s_warehouse = None
            row.t_warehouse = wo.fg_warehouse

        # remove temporary attribute if present
        if hasattr(row, "_c4_role"):
            delattr(row, "_c4_role")

    return se.as_dict()


def _get_transferred_items_to_wip(work_order_name, wip_warehouse):
    """
    Get total qty moved INTO WIP for this Work Order via
    'Material Transfer for Manufacture' Stock Entries.

    Returns list of dicts:
    [
        {"item_code": ..., "stock_uom": ..., "qty": ...},
        ...
    ]
    """
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
        return []

    rows = frappe.get_all(
        "Stock Entry Detail",
        filters={
            "parent": ["in", se_names],
            "t_warehouse": wip_warehouse,
        },
        fields=["item_code", "stock_uom", "qty"],
    )

    if not rows:
        return []

    aggregated = {}
    for r in rows:
        key = (r["item_code"], r["stock_uom"])
        aggregated.setdefault(key, 0.0)
        aggregated[key] += float(r["qty"] or 0.0)

    result = []
    for (item_code, stock_uom), total_qty in aggregated.items():
        if total_qty <= 0:
            continue
        result.append({
            "item_code": item_code,
            "stock_uom": stock_uom,
            "qty": total_qty,
        })

    return result
