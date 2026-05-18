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
    has_workstation = jc_meta.has_field("workstation")
    has_operation = jc_meta.has_field("operation")

    fields = ["name", "status"]
    if has_total_operating_cost:
        fields.append("total_operating_cost")
    if has_total_time_in_mins:
        fields.append("total_time_in_mins")
    if has_hour_rate:
        fields.append("hour_rate")
    if has_workstation:
        fields.append("workstation")
    if has_operation:
        fields.append("operation")
    for fieldname in ("total_completed_qty", "completed_qty", "for_quantity"):
        if jc_meta.has_field(fieldname):
            fields.append(fieldname)

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

        cost = _get_job_card_cost_from_time_logs(jc.get("name"))
        if cost > 0:
            total += cost
            continue

        cost = _get_job_card_cost_from_work_order_operation(work_order_name, jc)
        if cost > 0:
            total += cost
            continue

        mins = flt(jc.get("total_time_in_mins"))
        rate = _get_job_card_hour_rate(jc)
        if mins > 0 and rate > 0:
            total += (mins / 60.0) * rate

    return total


def _get_job_card_cost_from_work_order_operation(work_order_name: str, jc_row) -> float:
    """
    Price a completed Job Card from the matching Work Order operation.

    Some C4 flows complete Job Cards by quantity without recording a time log.
    In that case, the Job Card is still the real operation signal, and the
    Work Order operation row provides the rate/time basis.
    """
    if not work_order_name or not jc_row:
        return 0.0

    completed_qty = _get_job_card_completed_qty(jc_row)
    if completed_qty <= 0:
        return 0.0

    operation = jc_row.get("operation")
    workstation = jc_row.get("workstation")

    wo_op_meta = frappe.get_meta("Work Order Operation")
    wo_op_fields = _get_existing_fields(
        wo_op_meta,
        [
            "name",
            "operation",
            "workstation",
            "time_in_mins",
            "hour_rate",
            "planned_operating_cost",
            "actual_operating_cost",
            "completed_qty",
        ],
    )

    filters = {"parent": work_order_name, "parenttype": "Work Order"}
    if operation and wo_op_meta.has_field("operation"):
        filters["operation"] = operation
    if workstation and wo_op_meta.has_field("workstation"):
        filters["workstation"] = workstation

    rows = frappe.get_all(
        "Work Order Operation",
        filters=filters,
        fields=wo_op_fields,
        order_by="idx asc",
    )

    if not rows and operation and wo_op_meta.has_field("operation"):
        rows = frappe.get_all(
            "Work Order Operation",
            filters={
                "parent": work_order_name,
                "parenttype": "Work Order",
                "operation": operation,
            },
            fields=wo_op_fields,
            order_by="idx asc",
        )

    if not rows:
        return 0.0

    op = rows[0]
    cost = flt(op.get("actual_operating_cost")) or flt(op.get("planned_operating_cost"))
    op_completed_qty = flt(op.get("completed_qty"))

    if cost > 0 and op_completed_qty > 0:
        return cost * min(completed_qty / op_completed_qty, 1.0)

    mins = flt(op.get("time_in_mins"))
    rate = flt(op.get("hour_rate")) or _get_job_card_hour_rate(jc_row)
    if mins <= 0 or rate <= 0:
        return 0.0

    wo_qty = flt(frappe.db.get_value("Work Order", work_order_name, "qty"))
    qty_basis = op_completed_qty or wo_qty or completed_qty
    qty_share = (completed_qty / qty_basis) if qty_basis > 0 else 1.0

    return (mins / 60.0) * rate * qty_share


def _get_existing_fields(meta, fieldnames: list[str]) -> list[str]:
    """Return only field names available on a DocType, keeping `name`."""
    fields = []
    for fieldname in fieldnames:
        if fieldname == "name" or meta.has_field(fieldname):
            fields.append(fieldname)

    return fields


def _get_job_card_completed_qty(job_card) -> float:
    """Return the quantity that this Job Card actually completed."""
    for fieldname in ("total_completed_qty", "completed_qty"):
        qty = flt(job_card.get(fieldname))
        if qty > 0:
            return qty

    if (job_card.get("status") or "").strip() == "Completed":
        return flt(job_card.get("for_quantity"))

    return 0.0


def _get_job_card_cost_from_time_logs(job_card_name: str) -> float:
    """Calculate actual Job Card cost from its recorded time logs."""
    if not job_card_name:
        return 0.0

    try:
        job_card = frappe.get_doc("Job Card", job_card_name)
    except Exception:
        return 0.0

    parent_rate = _get_job_card_hour_rate(job_card)
    total = 0.0

    for row in job_card.get("time_logs") or []:
        direct_cost = (
            flt(row.get("operating_cost"))
            or flt(row.get("operation_cost"))
            or flt(row.get("cost"))
            or flt(row.get("amount"))
        )
        if direct_cost > 0:
            total += direct_cost
            continue

        mins = flt(row.get("time_in_mins")) or flt(row.get("total_time_in_mins"))
        rate = flt(row.get("hour_rate")) or flt(row.get("hourly_rate")) or parent_rate

        if mins > 0 and rate > 0:
            total += (mins / 60.0) * rate

    return total


def _get_job_card_hour_rate(job_card) -> float:
    """Resolve an hourly operation rate from Job Card, Workstation, or Operation."""
    if not job_card:
        return 0.0

    rate = flt(job_card.get("hour_rate")) or flt(job_card.get("hourly_rate"))
    if rate > 0:
        return rate

    workstation = job_card.get("workstation")
    if workstation:
        rate = _get_hour_rate_from_doctype("Workstation", workstation)
        if rate > 0:
            return rate

    operation = job_card.get("operation")
    if operation:
        rate = _get_hour_rate_from_doctype("Operation", operation)
        if rate > 0:
            return rate

    return 0.0


def _get_hour_rate_from_doctype(doctype: str, name: str) -> float:
    """Read a rate field only when the target DocType has it."""
    if not doctype or not name:
        return 0.0

    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return 0.0

    for fieldname in ("hour_rate", "hourly_rate"):
        if not meta.has_field(fieldname):
            continue

        rate = flt(frappe.db.get_value(doctype, name, fieldname))
        if rate > 0:
            return rate

    return 0.0


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


@frappe.whitelist()
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
