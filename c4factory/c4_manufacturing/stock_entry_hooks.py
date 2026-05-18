from __future__ import annotations

import frappe
from frappe import _
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
        Keep warehouse mapping consistent for manufacturing entries.

        - Material Transfer for Manufacture:
            default missing target warehouse from Work Order.wip_warehouse.
        - Manufacture:
            raw rows must be source-only; finished/scrap rows must be target-only.
    """
    se_type = (doc.stock_entry_type or doc.purpose or "").strip()

    if se_type not in ("Material Transfer for Manufacture", "Manufacture"):
        return

    if not doc.work_order:
        return

    wo = frappe.get_doc("Work Order", doc.work_order)

    if se_type == "Material Transfer for Manufacture":
        if not wo.wip_warehouse:
            return

        for row in doc.items:
            if not row.t_warehouse:
                row.t_warehouse = wo.wip_warehouse

        return

    # Manufacture only: determine finished quantity robustly.
    # In some flows (e.g. Job Card), header fields may carry the actual qty
    # while row qty is still empty during early validate.
    row_finished_qty = 0.0
    finished_rows = []
    for row in doc.items:
        if flt(row.get("is_finished_item")) == 1 and flt(row.get("is_scrap_item")) != 1:
            finished_rows.append(row)
            row_qty = flt(row.get("qty")) or flt(row.get("transfer_qty"))
            if row_qty < 0:
                row_qty = abs(row_qty)
                row.qty = row_qty
            row_finished_qty += row_qty

    header_finished_qty = (
        flt(getattr(doc, "fg_completed_qty", 0))
        or flt(getattr(doc, "manufactured_qty", 0))
        or flt(getattr(doc, "for_quantity", 0))
    )

    finished_qty = row_finished_qty or header_finished_qty

    # If we have a finished qty at header but row qty is empty, sync first row.
    if row_finished_qty <= 0 and header_finished_qty > 0 and finished_rows:
        finished_rows[0].qty = header_finished_qty
        row_finished_qty = header_finished_qty
        finished_qty = header_finished_qty

    # Hard-fail only before submit when quantity is still truly missing.
    if finished_qty <= 0:
        if method == "before_submit":
            frappe.throw(
                _(
                    "Manufacture Stock Entry only: Finished item quantity is missing. "
                    "Please add a finished item row with Qty greater than 0."
                )
            )
        return

    doc.fg_completed_qty = finished_qty
    if hasattr(doc, "for_quantity"):
        doc.for_quantity = finished_qty
    if hasattr(doc, "manufactured_qty"):
        doc.manufactured_qty = finished_qty

    # Manufacture only: normalize warehouses and provide clear message
    # before ERPNext raises the generic same source/target alert.
    for row in doc.items:
        is_finished = flt(row.get("is_finished_item")) == 1
        is_scrap = flt(row.get("is_scrap_item")) == 1

        if is_finished or is_scrap:
            row.s_warehouse = None
        else:
            row.t_warehouse = None

        if row.s_warehouse and row.t_warehouse and row.s_warehouse == row.t_warehouse:
            frappe.throw(
                _(
                    "Manufacture Stock Entry only: Row {0} has same Source and Target Warehouse. "
                    "Raw material rows must have Source only, while Finished/Scrap rows must have Target only."
                ).format(row.idx)
            )

    # Manufacture only: set finished-item valuation from actual consumed
    # material + allocated Job Card operating cost.
    _set_manufacture_finished_item_valuation(doc, wo)


def _set_manufacture_finished_item_valuation(doc, wo_doc) -> None:
    """
    For Manufacture entries, compute finished-item basic_rate as:
      (raw_consumed_material_cost + allocated_operation_cost) / finished_qty

    - raw cost is taken from raw rows in this Stock Entry.
    - operation cost is taken from actual Job Card totals for the Work Order,
      allocated to this SE by produced quantity share.
    """
    se_type = (doc.stock_entry_type or doc.purpose or "").strip()
    if se_type != "Manufacture":
        return

    finished_rows = []
    raw_material_cost = 0.0

    for row in doc.items or []:
        is_finished = flt(row.get("is_finished_item")) == 1
        is_scrap = flt(row.get("is_scrap_item")) == 1

        qty = abs(flt(row.get("transfer_qty")) or flt(row.get("qty")))

        if is_finished and not is_scrap:
            finished_rows.append(row)
            continue

        if is_scrap:
            continue

        # Prefer explicit row amount, fallback to qty * basic_rate
        amount = abs(flt(row.get("basic_amount") or row.get("amount")))
        if amount <= 0 and qty > 0:
            amount = qty * abs(flt(row.get("basic_rate")))
        raw_material_cost += amount

    finished_qty = sum(
        abs(flt(r.get("transfer_qty")) or flt(r.get("qty"))) for r in finished_rows
    )
    if finished_qty <= 0:
        return

    wo_qty = max(flt(getattr(wo_doc, "qty", 0)), 0.0)
    wo_produced_before = max(flt(getattr(wo_doc, "produced_qty", 0)), 0.0)
    wo_produced_after = max(wo_produced_before + finished_qty, finished_qty)

    total_op_cost = _get_work_order_operating_cost_from_job_cards(wo_doc.name)

    # Allocate operation cost to this finish quantity.
    op_basis_qty = wo_produced_after if wo_produced_after > 0 else wo_qty
    op_share = (finished_qty / op_basis_qty) if op_basis_qty > 0 else 0.0
    allocated_op_cost = total_op_cost * op_share

    total_fg_amount = raw_material_cost + allocated_op_cost
    fg_rate = (total_fg_amount / finished_qty) if finished_qty > 0 else 0.0

    for row in finished_rows:
        row_qty = abs(flt(row.get("transfer_qty")) or flt(row.get("qty")))
        if row_qty <= 0:
            continue
        row.qty = row_qty
        row.basic_rate = fg_rate
        if hasattr(row, "valuation_rate"):
            row.valuation_rate = fg_rate


def _get_work_order_operating_cost_from_job_cards(work_order_name: str) -> float:
    """Return actual operating cost from Job Cards linked to the Work Order."""
    if not work_order_name:
        return 0.0

    try:
        jc_meta = frappe.get_meta("Job Card")
    except Exception:
        return 0.0

    has_total_operating_cost = jc_meta.has_field("total_operating_cost")
    has_total_time_in_mins = jc_meta.has_field("total_time_in_mins")
    has_hour_rate = jc_meta.has_field("hour_rate")

    fields = ["name", "status"]
    if has_total_operating_cost:
        fields.append("total_operating_cost")
    if has_total_time_in_mins:
        fields.append("total_time_in_mins")
    if has_hour_rate:
        fields.append("hour_rate")

    jc_rows = frappe.get_all(
        "Job Card",
        filters={
            "work_order": work_order_name,
            "docstatus": ["<", 2],
        },
        fields=fields,
    )

    total = 0.0
    for jc in jc_rows:
        status = (jc.get("status") or "").strip()
        if status == "Cancelled":
            continue

        cost = flt(jc.get("total_operating_cost"))
        if cost > 0:
            total += cost
            continue

        mins = flt(jc.get("total_time_in_mins"))
        rate = flt(jc.get("hour_rate"))
        if mins > 0 and rate > 0:
            total += (mins / 60.0) * rate

    return total


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
    Aggregate actual material/scrap cost for the given Work Order from all
    submitted Stock Entries and combine with actual Job Card operating cost.

    Logic:
      - Look at all submitted Stock Entries with se.work_order = WO
      - For each Stock Entry Detail row:
          * ignore finished items (is_finished_item = 1)
          * if is_scrap_item = 1 → goes to Scrap Material Cost
          * else → goes to Raw Material Cost
      - Use transfer_qty * basic_rate as the amount
    - Operating Cost = sum of actual Job Card operating cost
    - Total Cost = Raw + Operating - Scrap
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
        qty = abs(flt(r.transfer_qty))
        rate = abs(flt(r.basic_rate))
        amount = qty * rate

        # finished item cost is not counted here (it is the result)
        if r.is_scrap_item:
            scrap_material_cost += amount
        elif not r.is_finished_item:
            raw_material_cost += amount

    # Operating cost from actual Job Cards linked to the Work Order
    operating_cost = _get_work_order_operating_cost_from_job_cards(work_order_name)

    # Write back to Work Order custom fields
    wo.db_set("c4_raw_material_cost", raw_material_cost)
    wo.db_set("c4_scrap_material_cost", scrap_material_cost)
    wo.db_set("c4_operating_cost", operating_cost)
    wo.db_set(
        "c4_total_cost",
        raw_material_cost + operating_cost - scrap_material_cost,
    )
