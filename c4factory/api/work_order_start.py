from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cstr, flt

from c4factory.api.work_order_pick_list import is_continuous_manufacture_item


REALTIME_EVENT = "c4factory_continuous_start"


@frappe.whitelist()
def get_continuous_start_context(work_order: str) -> dict:
    """Return whether a continuous transfer can be started and its maximum qty."""
    wo = frappe.get_doc("Work Order", work_order)
    wo.check_permission("read")

    eligible_rows = _get_eligible_rows(wo)
    transferred_qty = _get_continuous_transferred_qty(wo.name)
    return {
        "has_eligible_items": bool(eligible_rows),
        "remaining_qty": max(flt(wo.qty) - transferred_qty, 0.0),
        "pending": bool(wo.get("custom_continuous_start_pending")),
    }


@frappe.whitelist()
def enqueue_continuous_start_transfer(work_order: str, qty: float) -> dict:
    """Reserve and enqueue one idempotent continuous-material Start request."""
    qty = flt(qty)
    if qty <= 0:
        frappe.throw(_("Start quantity must be greater than zero."))

    wo = frappe.get_doc("Work Order", work_order)
    wo.check_permission("read")
    if not frappe.has_permission("Stock Entry", "create"):
        frappe.throw(_("You do not have permission to create Stock Entries."))
    if not frappe.has_permission("Stock Entry", "submit"):
        frappe.throw(_("You do not have permission to submit Stock Entries."))
    _validate_work_order(wo)

    if not _get_eligible_rows(wo):
        return {
            "status": "no_items",
            "message": _(
                "No continuous-manufacture items were found. No Stock Entry was created."
            ),
        }

    # Serialize Start clicks for this Work Order. Reading the flag in the same
    # SELECT ... FOR UPDATE prevents two requests from being queued concurrently.
    locked = frappe.db.sql(
        """
        SELECT custom_continuous_start_pending,
               custom_continuous_start_request_id
        FROM `tabWork Order`
        WHERE name = %s
        FOR UPDATE
        """,
        (wo.name,),
        as_dict=True,
    )
    if not locked:
        frappe.throw(_("Work Order {0} does not exist.").format(wo.name))
    if locked[0].custom_continuous_start_pending:
        return {
            "status": "already_queued",
            "message": _(
                "A continuous-material Stock Entry is already being created for this Work Order."
            ),
        }

    remaining_qty = max(flt(wo.qty) - _get_continuous_transferred_qty(wo.name), 0.0)
    if qty > remaining_qty + 0.000001:
        frappe.throw(
            _("Start quantity {0} exceeds the remaining quantity {1}.").format(
                qty,
                remaining_qty,
            )
        )

    request_id = frappe.generate_hash(length=20)
    frappe.db.set_value(
        "Work Order",
        wo.name,
        {
            "custom_continuous_start_pending": 1,
            "custom_continuous_start_request_id": request_id,
        },
        update_modified=False,
    )

    frappe.enqueue(
        "c4factory.api.work_order_start.create_continuous_start_stock_entry",
        queue="default",
        timeout=900,
        enqueue_after_commit=True,
        job_id=f"c4-continuous-start-{request_id}",
        deduplicate=True,
        work_order=wo.name,
        qty=qty,
        request_id=request_id,
        initiated_by=frappe.session.user,
    )
    return {
        "status": "queued",
        "request_id": request_id,
        "message": _("Stock Entry creation started in the background."),
    }


def create_continuous_start_stock_entry(
    work_order: str,
    qty: float,
    request_id: str,
    initiated_by: str,
) -> None:
    """Background job: create, submit, and report a continuous-material transfer."""
    try:
        existing = frappe.db.get_value(
            "Stock Entry",
            {
                "custom_continuous_start_request_id": request_id,
                "docstatus": 1,
            },
            "name",
        )
        if existing:
            _clear_pending_request(work_order, request_id)
            frappe.db.commit()
            _publish_result(
                initiated_by,
                work_order,
                "success",
                _("Stock Entry {0} was created and submitted successfully.").format(
                    existing
                ),
                stock_entry=existing,
            )
            return

        wo = frappe.get_doc("Work Order", work_order)
        _validate_work_order(wo)
        eligible_rows = _get_eligible_rows(wo)
        if not eligible_rows:
            _clear_pending_request(wo.name, request_id)
            frappe.db.commit()
            _publish_result(
                initiated_by,
                wo.name,
                "no_items",
                _(
                    "No continuous-manufacture items were found. No Stock Entry was created."
                ),
            )
            return

        qty = flt(qty)
        remaining_qty = max(
            flt(wo.qty) - _get_continuous_transferred_qty(wo.name),
            0.0,
        )
        if qty <= 0 or qty > remaining_qty + 0.000001:
            frappe.throw(
                _("Start quantity {0} exceeds the remaining quantity {1}.").format(
                    qty,
                    remaining_qty,
                )
            )

        stock_entry = _build_stock_entry(wo, eligible_rows, qty, request_id)
        stock_entry.insert()
        stock_entry.submit()
        started_work_order = frappe.get_doc("Work Order", wo.name)
        started_work_order.set_status()

        _clear_pending_request(wo.name, request_id)
        frappe.db.commit()
        _publish_result(
            initiated_by,
            wo.name,
            "success",
            _("Stock Entry {0} was created and submitted successfully.").format(
                stock_entry.name
            ),
            stock_entry=stock_entry.name,
        )
    except Exception as exc:
        error_message = cstr(exc) or _("Unable to create the Stock Entry.")
        traceback = frappe.get_traceback()
        frappe.db.rollback()
        _clear_pending_request(work_order, request_id)
        frappe.db.commit()
        frappe.log_error(
            traceback,
            f"C4Factory continuous Start failed ({work_order})",
        )
        _publish_result(
            initiated_by,
            work_order,
            "error",
            error_message,
        )


def _build_stock_entry(wo, eligible_rows, qty: float, request_id: str):
    if not wo.get("wip_warehouse"):
        frappe.throw(
            _("Work-in-Progress Warehouse is required for Work Order {0}.").format(
                wo.name
            )
        )

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer for Manufacture"
    se.purpose = "Material Transfer for Manufacture"
    se.company = wo.company
    se.work_order = wo.name
    se.from_bom = 0
    se.fg_completed_qty = qty
    se.custom_continuous_manufacture_transfer = 1
    se.custom_continuous_start_request_id = request_id
    if se.meta.has_field("custom_work_order"):
        se.custom_work_order = wo.name
    if se.meta.has_field("to_warehouse"):
        se.to_warehouse = wo.wip_warehouse

    quantity_scale = qty / (flt(wo.qty) or 1.0)
    for wo_row, item_group in eligible_rows:
        group = frappe.get_cached_doc("Item Group", item_group)
        source_warehouse = group.get("custom_warehouse")
        if not source_warehouse:
            frappe.throw(
                _("Manufacture Warehouse is required for Item Group {0}.").format(
                    frappe.bold(item_group)
                )
            )

        row_qty = flt(wo_row.get("required_qty") or wo_row.get("qty")) * quantity_scale
        if row_qty <= 0:
            continue

        stock_uom = (
            wo_row.get("stock_uom")
            or wo_row.get("uom")
            or frappe.db.get_value("Item", wo_row.item_code, "stock_uom")
        )
        se_row = se.append(
            "items",
            {
                "item_code": wo_row.item_code,
                "qty": row_qty,
                "uom": stock_uom,
                "stock_uom": stock_uom,
                "conversion_factor": 1,
                "s_warehouse": source_warehouse,
                "t_warehouse": wo.wip_warehouse,
                "is_finished_item": 0,
                "is_scrap_item": 0,
            },
        )
        if se_row.meta.has_field("custom_work_order_item"):
            se_row.custom_work_order_item = wo_row.name
        se_row._c4_source_warehouse = source_warehouse
        se_row._c4_qty = row_qty

    if not se.get("items"):
        frappe.throw(
            _("No continuous-manufacture items were found. No Stock Entry was created.")
        )

    se.set_missing_values()
    for row in se.items:
        row.s_warehouse = row._c4_source_warehouse
        row.t_warehouse = wo.wip_warehouse
        row.qty = row._c4_qty
        delattr(row, "_c4_source_warehouse")
        delattr(row, "_c4_qty")

    return se


def _get_eligible_rows(wo) -> list[tuple[object, str]]:
    item_group_cache = {}
    continuous_group_cache = {}
    eligible = []

    for row in wo.get("required_items") or wo.get("items") or []:
        item_code = row.get("item_code")
        if not item_code or flt(row.get("required_qty") or row.get("qty")) <= 0:
            continue

        if not is_continuous_manufacture_item(
            row,
            item_group_cache=item_group_cache,
            continuous_group_cache=continuous_group_cache,
        ):
            continue

        item_group = row.get("item_group") or item_group_cache.get(item_code)
        if item_group:
            eligible.append((row, item_group))

    return eligible


def _get_continuous_transferred_qty(work_order: str) -> float:
    return flt(
        frappe.db.sql(
            """
            SELECT COALESCE(SUM(fg_completed_qty), 0)
            FROM `tabStock Entry`
            WHERE work_order = %s
              AND docstatus = 1
              AND COALESCE(custom_continuous_manufacture_transfer, 0) = 1
              AND (stock_entry_type = 'Material Transfer for Manufacture'
                   OR purpose = 'Material Transfer for Manufacture')
            """,
            (work_order,),
        )[0][0]
    )


def _validate_work_order(wo) -> None:
    if wo.docstatus != 1:
        frappe.throw(_("Work Order must be submitted before it can be started."))
    if wo.get("status") in {"Stopped", "Closed", "Completed", "Cancelled"}:
        frappe.throw(
            _("Work Order {0} cannot be started while its status is {1}.").format(
                wo.name,
                wo.status,
            )
        )
    if not wo.get("wip_warehouse"):
        frappe.throw(
            _("Work-in-Progress Warehouse is required for Work Order {0}.").format(
                wo.name
            )
        )


def _clear_pending_request(work_order: str, request_id: str) -> None:
    current_request = frappe.db.get_value(
        "Work Order",
        work_order,
        "custom_continuous_start_request_id",
    )
    if current_request != request_id:
        return

    frappe.db.set_value(
        "Work Order",
        work_order,
        {
            "custom_continuous_start_pending": 0,
            "custom_continuous_start_request_id": None,
        },
        update_modified=False,
    )


def _publish_result(
    user: str,
    work_order: str,
    status: str,
    message: str,
    stock_entry: str | None = None,
) -> None:
    try:
        frappe.publish_realtime(
            REALTIME_EVENT,
            {
                "work_order": work_order,
                "status": status,
                "message": message,
                "stock_entry": stock_entry,
            },
            user=user,
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"C4Factory continuous Start notification failed ({work_order})",
        )
