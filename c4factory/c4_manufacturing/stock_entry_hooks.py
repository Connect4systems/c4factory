from __future__ import annotations

import frappe
from frappe.utils import flt


# ============================================================
# Helper: get WO items table regardless of field name
# ============================================================

def _get_wo_items(wo_doc):
    """Return the Work Order items grid (v15 uses required_items)."""
    return wo_doc.get("required_items") or wo_doc.get("items") or []


# ============================================================
# 1) Stock Entry.validate – default WIP target warehouse
# ============================================================

def set_wip_target_warehouse(doc, method: str | None = None) -> None:
    """
    If Stock Entry Type is 'Material Transfer for Manufacture' or 'Manufacture'
    and a line has no t_warehouse, pull it from Work Order.wip_warehouse.
    """
    se_type = (doc.stock_entry_type or doc.purpose or "").strip()

    if se_type not in ("Material Transfer for Manufacture", "Manufacture"):
        return

    if not doc.work_order:
        return

    wo = frappe.get_doc("Work Order", doc.work_order)
    if not wo.wip_warehouse:
        return

    for row in doc.items:
        if not row.t_warehouse:
            row.t_warehouse = wo.wip_warehouse


# ============================================================
# 2) Work Order costing from submitted Stock Entries
# ============================================================

def on_submit_update_work_order_costing(doc, method: str | None = None) -> None:
    """
    Called on Stock Entry submit.
    Recalculate the Work Order costing (raw / scrap / total) from all
    submitted Stock Entries linked to this Work Order.
    """
    if not doc.work_order:
        return

    _recalculate_work_order_costs(doc.work_order)


def recompute_work_order_costing(work_order_name: str) -> None:
    """
    Public helper for other modules (e.g. on Stock Entry cancel)
    to recompute costing.
    """
    if not work_order_name:
        return

    _recalculate_work_order_costs(work_order_name)


def _recalculate_work_order_costs(work_order_name: str) -> None:
    """
    Aggregate actual material cost for the given Work Order from all
    submitted Stock Entries.

    Logic:
      - Look at all submitted Stock Entries with se.work_order = WO
      - For each Stock Entry Detail row:
          * ignore finished items (is_finished_item = 1)
          * if is_scrap_item = 1 → goes to Scrap Material Cost
          * else → goes to Raw Material Cost
      - Use transfer_qty * basic_rate as the amount
      - Total Cost = Raw + Scrap + Operating Cost (entered manually on WO)
    """
    wo = frappe.get_doc("Work Order", work_order_name)

    # Fetch all Stock Entry rows for this Work Order
    rows = frappe.db.sql(
        """
        SELECT
            sed.is_finished_item,
            sed.is_scrap_item,
            sed.transfer_qty,
            sed.basic_rate,
            se.stock_entry_type
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se
            ON se.name = sed.parent
        WHERE
            se.docstatus = 1
            AND se.work_order = %s
        """,
        (work_order_name,),
        as_dict=True,
    )

    raw_material_cost = 0.0
    scrap_material_cost = 0.0

    for r in rows:
        qty = flt(r.transfer_qty)
        rate = flt(r.basic_rate)
        amount = qty * rate

        # finished item cost is not counted here (it is the result)
        if r.is_scrap_item:
            scrap_material_cost += amount
        elif not r.is_finished_item:
            raw_material_cost += amount

    # Operating cost is entered on the Work Order manually
    operating_cost = flt(wo.c4_operating_cost)

    # Write back to Work Order custom fields
    wo.db_set("c4_raw_material_cost", raw_material_cost)
    wo.db_set("c4_scrap_material_cost", scrap_material_cost)
    wo.db_set(
        "c4_total_cost",
        raw_material_cost + scrap_material_cost + operating_cost,
    )
