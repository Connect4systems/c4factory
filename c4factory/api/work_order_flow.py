from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from c4factory.c4_manufacturing.work_order_hooks import get_default_source_warehouse


# ================================================================
# Work Order helpers and hooks
# ================================================================


def _get_wo_items(wo_doc):
    """Return the Work Order items table (v15 uses required_items)."""
    return wo_doc.get("required_items") or wo_doc.get("items") or []


def _update_wo_item_balances(wo_doc):
    """
    Update internal balance fields for Work Order items only.
    Does NOT write to the database directly.
    """
    total_transferred = 0.0
    total_consumed = 0.0

    for row in _get_wo_items(wo_doc):
        req = flt(row.get("required_qty"))
        transferred = flt(row.get("transferred_qty"))
        consumed = flt(row.get("consumed_qty"))

        total_transferred += transferred
        total_consumed += consumed

        # Optional custom fields on Work Order Item
        if hasattr(row, "custom_balance_to_transfer"):
            row.custom_balance_to_transfer = max(req - transferred, 0.0)
        if hasattr(row, "custom_balance_to_consume"):
            row.custom_balance_to_consume = max(req - consumed, 0.0)

    # Optional summary fields on Work Order header
    if hasattr(wo_doc, "custom_total_transferred_qty"):
        wo_doc.custom_total_transferred_qty = total_transferred
    if hasattr(wo_doc, "custom_total_consumed_qty"):
        wo_doc.custom_total_consumed_qty = total_consumed


def _update_wo_status(wo_doc):
    """Call set_status if available."""
    try:
        if hasattr(wo_doc, "set_status"):
            wo_doc.set_status()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "C4Factory: update_wo_status error")


def on_work_order_validate(doc, method=None):
    """Hook: Work Order.validate"""
    _update_wo_item_balances(doc)


def on_work_order_submit(doc, method=None):
    """Hook: Work Order.on_submit"""
    _update_wo_item_balances(doc)
    _update_wo_status(doc)


# ================================================================
# Pick List balance map
# ================================================================


def _get_pick_list_balances_map(pl_doc_or_name):
    """
    Build a balance map for each Pick List Item row.

    Returns dict:
      {
        "<pl_item_name>": {
            "pl_qty": float,
            "transferred": float,
            "balance": float,
            "item_code": str,
            "item_name": str,
        },
        ...
      }
    """
    if isinstance(pl_doc_or_name, str):
        pl = frappe.get_doc("Pick List", pl_doc_or_name)
    else:
        pl = pl_doc_or_name

    locations = pl.get("locations") or []
    if not locations:
        return {}

    result = {}

    # Base quantities from Pick List
    for row in locations:
        # Prefer custom_pl_qty if present, otherwise use qty
        pl_qty = flt(getattr(row, "custom_pl_qty", None)) or flt(row.get("qty"))
        result[row.name] = {
            "pl_qty": pl_qty,
            "transferred": 0.0,
            "balance": pl_qty,
            "item_code": row.item_code,
            "item_name": row.item_name,
        }

    # Sum transferred qty from submitted Stock Entry Detail
    # using custom_pick_list_item field.
    transferred_rows = frappe.db.sql(
        """
        SELECT sed.custom_pick_list_item, COALESCE(SUM(sed.qty), 0) AS total_qty
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.docstatus = 1
          AND se.pick_list = %(pick_list)s
          AND sed.custom_pick_list_item IS NOT NULL
        GROUP BY sed.custom_pick_list_item
        """,
        {"pick_list": pl.name},
        as_dict=True,
    )

    for row in transferred_rows:
        pl_item_name = row.custom_pick_list_item
        if pl_item_name in result:
            transferred = flt(row.total_qty)
            result[pl_item_name]["transferred"] = transferred

    # Backward compatibility path:
    # some Stock Entries are linked to Pick List only at header level
    # (se.pick_list) without row-level custom_pick_list_item.
    # In that case, distribute unlinked transferred qty by item_code
    # across matching Pick List rows in row order.
    unlinked_rows = frappe.db.sql(
        """
        SELECT sed.item_code, COALESCE(SUM(sed.qty), 0) AS total_qty
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.docstatus = 1
          AND se.pick_list = %(pick_list)s
          AND (sed.custom_pick_list_item IS NULL OR sed.custom_pick_list_item = '')
        GROUP BY sed.item_code
        """,
        {"pick_list": pl.name},
        as_dict=True,
    )

    rows_by_item_code = {}
    for row in locations:
        if row.name not in result:
            continue
        rows_by_item_code.setdefault(row.item_code, []).append(row.name)

    for row in unlinked_rows:
        item_code = row.item_code
        remaining = flt(row.total_qty)
        if remaining <= 0:
            continue

        for pl_item_name in rows_by_item_code.get(item_code, []):
            info = result.get(pl_item_name)
            if not info:
                continue

            free_qty = max(flt(info["pl_qty"]) - flt(info["transferred"]), 0.0)
            if free_qty <= 0:
                continue

            alloc = min(remaining, free_qty)
            info["transferred"] = flt(info["transferred"]) + alloc
            remaining -= alloc

            if remaining <= 0.000001:
                break

    for info in result.values():
        info["balance"] = max(flt(info["pl_qty"]) - flt(info["transferred"]), 0.0)

    return result


def _update_pick_list_status_from_db(pick_list_name: str):
    """
    Update Pick List.status based on current balances:
    - If all balances are zero -> "Completed"
    - Otherwise -> "Open"
    """
    if not pick_list_name:
        return

    pl = frappe.get_doc("Pick List", pick_list_name)
    balances = _get_pick_list_balances_map(pl)

    has_balance = any(flt(info["balance"]) > 0.000001 for info in balances.values())
    new_status = "Open" if has_balance else "Completed"

    try:
        frappe.db.set_value("Pick List", pl.name, "status", new_status)
        pl.status = new_status
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), "C4Factory: update_pick_list_status_from_db error"
        )


# ================================================================
# Public API: get_pick_list_balance_rows
# ================================================================


@frappe.whitelist()
def get_pick_list_balance_rows(pick_list: str):
    """
    Return rows for the partial transfer dialog.

    Each row:
      {
        "pl_item_name": str,
        "item_code": str,
        "item_name": str,
        "balance_qty": float
      }
    """
    if not pick_list:
        frappe.throw(_("Pick List is required"))

    pl = frappe.get_doc("Pick List", pick_list)
    if pl.docstatus != 1:
        frappe.throw(_("Pick List {0} must be submitted").format(pl.name))

    balances = _get_pick_list_balances_map(pl)
    rows = []

    for pl_item_name, info in balances.items():
        balance = flt(info["balance"])
        if balance <= 0.000001:
            continue

        rows.append(
            {
                "pl_item_name": pl_item_name,
                "item_code": info.get("item_code"),
                "item_name": info.get("item_name"),
                "balance_qty": balance,
            }
        )

    return rows
# ---------------------------------------------------------
# Pick List – validate hook (called from hooks.py)
# ---------------------------------------------------------

def on_pick_list_validate(doc, method=None):
    """
    Keep Pick List source warehouses aligned with the same Item Group
    Defaults lookup used by Work Order required items.
    """
    action = getattr(doc, "_action", None)
    if doc.docstatus != 0 or action in {"submit", "update_after_submit", "cancel"}:
        return

    set_pick_list_warehouses_from_item_group(doc)


def set_pick_list_warehouses_from_item_group(doc):
    """
    For each Pick List Item, prefer Item Group Defaults -> default_warehouse.

    ERPNext may prefill Pick List Item.warehouse from stock availability. For
    manufacturing picks we want the warehouse mapping to follow the Item Group
    defaults, matching the Work Order source warehouse behavior.
    """
    locations = doc.get("locations") or []
    if not locations:
        return

    company = doc.get("company")
    item_group_cache = {}
    warehouse_cache = {}

    for row in locations:
        item_code = row.get("item_code")
        if not item_code:
            continue

        item_group = row.get("item_group") or item_group_cache.get(item_code)
        if item_group is None:
            item_group = frappe.db.get_value("Item", item_code, "item_group")
            item_group_cache[item_code] = item_group

        if not item_group:
            continue

        cache_key = (item_code, item_group, company)
        warehouse = warehouse_cache.get(cache_key)
        if warehouse is None:
            warehouse = get_default_source_warehouse(
                item_code=item_code,
                item_group=item_group,
                company=company,
            )
            warehouse_cache[cache_key] = warehouse

        if warehouse:
            row.warehouse = warehouse


# ================================================================
# Public API: create partial Stock Entry from Pick List
# ================================================================


@frappe.whitelist()
def make_partial_stock_entry_from_pick_list(pick_list: str, items_json: str) -> str:
    """
    Create a Material Transfer for Manufacture Stock Entry from a Pick List
    using partial quantities per row (<= balance).

    - Uses balance calculated by _get_pick_list_balances_map
    - Uses only the WIP Warehouse from the Work Order
    """
    if not pick_list:
        frappe.throw(_("Pick List is required"))

    pl = frappe.get_doc("Pick List", pick_list)
    if pl.docstatus != 1:
        frappe.throw(_("Pick List {0} must be submitted").format(pl.name))

    wo_name = pl.get("work_order")
    if not wo_name:
        frappe.throw(_("Pick List {0} is not linked to a Work Order").format(pl.name))

    wo = frappe.get_doc("Work Order", wo_name)

    if not wo.get("wip_warehouse"):
        frappe.throw(_("Work Order {0} has no WIP Warehouse set").format(wo.name))

    # Parse items from dialog
    items = frappe.parse_json(items_json) or []
    if not items:
        frappe.throw(_("No items were selected to transfer"))

    balances = _get_pick_list_balances_map(pl)
    pl_rows_by_name = {row.name: row for row in (pl.get("locations") or [])}

    # Create Stock Entry header
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer for Manufacture"
    se.company = pl.company
    se.pick_list = pl.name

    # Link to Work Order if field exists
    if hasattr(se, "work_order"):
        se.work_order = wo.name

    # Build items
    for row in items:
        pl_item_name = row.get("pl_item_name")
        qty = flt(row.get("qty"))

        if not pl_item_name or qty <= 0:
            continue

        pl_row = pl_rows_by_name.get(pl_item_name)
        if not pl_row:
            frappe.throw(_("Invalid Pick List Item {0}").format(pl_item_name))

        info = balances.get(pl_item_name) or {
            "pl_qty": 0.0,
            "transferred": 0.0,
            "balance": 0.0,
        }
        balance = flt(info["balance"])

        if qty > balance + 1e-9:
            frappe.throw(
                _("Item {0}: Transfer Qty ({1}) cannot exceed PL Balance ({2})").format(
                    pl_row.item_code, qty, balance
                )
            )

        item = se.append("items", {})
        item.item_code = pl_row.item_code
        item.item_name = pl_row.item_name
        item.uom = pl_row.uom
        item.qty = qty

        # From Pick List warehouse to Work Order WIP warehouse
        item.s_warehouse = pl_row.warehouse
        item.t_warehouse = wo.wip_warehouse

        # Optional link to PL item if custom field exists
        # (custom_pick_list_item on Stock Entry Detail)
        try:
            item.custom_pick_list_item = pl_row.name
        except Exception:
            pass
        try:
            item.custom_work_order_item = pl_row.get("custom_work_order_item")
        except Exception:
            pass

    if not se.get("items"):
        frappe.throw(_("No valid items to transfer for Work Order {0}").format(wo.name))

    se.insert(ignore_permissions=True)
    frappe.db.commit()

    return se.name


# ================================================================
# Stock Entry hooks (do NOT modify Stock Entry itself)
# ================================================================


def on_stock_entry_submit(doc, method=None):
    """
    Hook: Stock Entry.on_submit

    Do NOT modify or save the Stock Entry document here.
    Only update related Work Order and Pick List.
    """
    pl_name = doc.get("pick_list")
    if pl_name:
        try:
            _update_pick_list_status_from_db(pl_name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "C4Factory: on_stock_entry_submit (Pick List)"
            )

    wo_name = doc.get("work_order")
    if wo_name:
        try:
            _recompute_wo_material_transfer_from_pls(wo_name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "C4Factory: on_stock_entry_submit (WO)"
            )


from c4factory.c4_manufacturing.stock_entry_hooks import recompute_work_order_costing

# ================================================================
# Recompute Work Order.material_transferred_for_manufacturing
# ================================================================


def _recompute_wo_material_transfer_from_pls(wo_name: str):
    """
    Recompute Work Order.material_transferred_for_manufacturing from actual
    submitted material-transfer Stock Entry rows.
    """
    if not wo_name:
        return

    wo = frappe.get_doc("Work Order", wo_name)
    total_for_qty = _get_transferred_production_qty_from_stock_entries(wo_name)

    # Persist transferred qty without updating the document `modified` timestamp
    try:
        frappe.db.set_value(
            "Work Order",
            wo_name,
            "material_transferred_for_manufacturing",
            total_for_qty,
            update_modified=False,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "C4Factory: set material_transferred_for_manufacturing failed")

    # Update in-memory object and recompute balances/status.
    wo.material_transferred_for_manufacturing = total_for_qty
    _update_wo_item_balances(wo)

    # _update_wo_status will persist status (using update_modified=False in override)
    _update_wo_status(wo)

    # Do NOT call wo.save() here to avoid bumping the Work Order `modified`
    # timestamp which causes the client-side "Document has been modified" alert
    # when users have the Work Order open while Stock Entry is submitted.


@frappe.whitelist()
def sync_work_order_material_transfer(wo_name: str) -> float:
    """Manually refresh material_transferred_for_manufacturing for one WO."""
    _recompute_wo_material_transfer_from_pls(wo_name)
    return flt(
        frappe.db.get_value(
            "Work Order", wo_name, "material_transferred_for_manufacturing"
        )
    )


def _get_transferred_production_qty_from_stock_entries(wo_name: str) -> float:
    """
    Convert submitted PL material-transfer rows back to production quantity.

    Example: a Pick List is for 2 finished units, but only half of every row was
    moved by submitted Stock Entries. This returns 1, not the full PL for_qty.
    """
    rows = frappe.db.sql(
        """
        SELECT
            se.pick_list,
            sed.custom_pick_list_item,
            sed.item_code,
            COALESCE(SUM(ABS(sed.qty)), 0) AS transferred_qty
        FROM `tabStock Entry` se
        INNER JOIN `tabStock Entry Detail` sed
            ON sed.parent = se.name
        WHERE
            se.docstatus = 1
            AND se.work_order = %(wo)s
            AND se.pick_list IS NOT NULL
            AND se.pick_list != ''
            AND se.stock_entry_type = 'Material Transfer for Manufacture'
            AND COALESCE(sed.is_finished_item, 0) = 0
            AND COALESCE(sed.is_scrap_item, 0) = 0
        GROUP BY se.pick_list, sed.custom_pick_list_item, sed.item_code
        """,
        {"wo": wo_name},
        as_dict=True,
    )

    if not rows:
        return 0.0

    by_pick_list = {}
    for row in rows:
        by_pick_list.setdefault(row.pick_list, []).append(row)

    total = 0.0
    for pl_name, transfer_rows in by_pick_list.items():
        if not frappe.db.exists("Pick List", pl_name):
            continue

        try:
            pl = frappe.get_doc("Pick List", pl_name)
            row_ratios = _get_pick_list_transfer_ratios(pl, transfer_rows)
            if not row_ratios:
                continue

            pl_for_qty = (
                flt(pl.get("for_qty"))
                or flt(pl.get("custom_for_qty"))
                or flt(pl.get("qty"))
                or 0.0
            )
            total += min(row_ratios) * pl_for_qty
            _update_pick_list_status_from_db(pl_name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"C4Factory: transferred production qty failed ({pl_name})",
            )

    wo_qty = flt(frappe.db.get_value("Work Order", wo_name, "qty"))
    return min(total, wo_qty) if wo_qty > 0 else total


def _get_pick_list_transfer_ratios(pl, transfer_rows) -> list[float]:
    transfers_by_pl_item = {}
    transfers_by_item = {}
    for row in transfer_rows:
        transferred_qty = flt(row.get("transferred_qty"))
        if transferred_qty <= 0:
            continue

        pl_item = row.get("custom_pick_list_item")
        item_code = row.get("item_code")
        if pl_item:
            transfers_by_pl_item[pl_item] = (
                flt(transfers_by_pl_item.get(pl_item)) + transferred_qty
            )
        elif item_code:
            transfers_by_item[item_code] = (
                flt(transfers_by_item.get(item_code)) + transferred_qty
            )

    ratios = []
    for pl_row in pl.get("locations") or []:
        pl_qty = flt(pl_row.get("custom_pl_qty")) or flt(pl_row.get("qty"))
        if pl_qty <= 0:
            continue

        transferred_qty = flt(transfers_by_pl_item.get(pl_row.name))
        if transferred_qty <= 0:
            item_code = pl_row.get("item_code")
            transferred_qty = min(flt(transfers_by_item.get(item_code)), pl_qty)
            if item_code and transferred_qty > 0:
                transfers_by_item[item_code] -= transferred_qty

        ratios.append(min(transferred_qty / pl_qty, 1.0))

    return ratios

# ================================================================
# Stock Entry hooks: keep Pick List + Work Order in sync on cancel
# ================================================================


def on_stock_entry_cancel(doc, method=None):
    """
    Stock Entry.on_cancel hook.

    - Recompute Pick List balances/status and WO transferred qty.
    - Recompute WO costing.
    - Use background job to avoid transaction-timing issues.
    """
    # Recompute costing immediately (safe on cancel)
    if doc.work_order:
        try:
            recompute_work_order_costing(doc.work_order)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "C4Factory: on_stock_entry_cancel costing"
            )

    _recompute_links_for_stock_entry_doc(doc)


def on_stock_entry_trash(doc, method=None):
    """Keep Pick List and Work Order state correct when canceled SE is deleted."""
    _recompute_links_for_stock_entry_doc(doc)


def _recompute_links_for_stock_entry_doc(doc) -> None:
    pick_lists, work_orders = _get_stock_entry_related_links(doc)

    for pl in pick_lists:
        try:
            _update_pick_list_status_from_db(pl)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"C4Factory: recompute Stock Entry links (Pick List {pl})",
            )

    for wo in work_orders:
        try:
            _recompute_wo_material_transfer_from_pls(wo)
            recompute_work_order_costing(wo)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"C4Factory: recompute Stock Entry links (WO {wo})",
            )

    try:
        frappe.enqueue(
            "c4factory.api.work_order_flow.recompute_after_stock_entry_links",
            pick_lists=list(pick_lists),
            work_orders=list(work_orders),
            queue="short",
            enqueue_after_commit=True,
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), "C4Factory: Stock Entry link enqueue failed"
        )


def _get_stock_entry_related_links(doc) -> tuple[set[str], set[str]]:
    pick_lists = set()
    work_orders = set()

    if doc.get("pick_list"):
        pick_lists.add(doc.get("pick_list"))
    if doc.get("work_order"):
        work_orders.add(doc.get("work_order"))

    for row in doc.get("items") or []:
        pl_item_name = row.get("custom_pick_list_item")
        if not pl_item_name:
            continue

        pl_name = frappe.db.get_value("Pick List Item", pl_item_name, "parent")
        if not pl_name:
            continue

        pick_lists.add(pl_name)
        wo_name = frappe.db.get_value("Pick List", pl_name, "work_order")
        if wo_name:
            work_orders.add(wo_name)

    return pick_lists, work_orders


def recompute_after_stock_entry(se_name: str):
    """
    Background job.

    - Find all Pick Lists linked to this Stock Entry via the
      custom_pick_list_item link field on Stock Entry Detail.
    - For each Pick List, recompute its balances/status from DB.
    - For each related Work Order, recompute the transferred qty
      from all submitted Pick Lists.
    """
    try:
        se = frappe.get_doc("Stock Entry", se_name)
    except frappe.DoesNotExistError:
        return

    # Only care about Material Transfer for Manufacture
    se_type = (se.get("stock_entry_type") or se.get("purpose") or "").strip()
    if se_type != "Material Transfer for Manufacture":
        return

    pick_lists = set()
    work_orders = set()

    for row in se.get("items") or []:
        pl_item_name = row.get("custom_pick_list_item")
        if not pl_item_name:
            continue

        pl_name = frappe.db.get_value("Pick List Item", pl_item_name, "parent")
        if not pl_name:
            continue

        pick_lists.add(pl_name)

        wo_name = frappe.db.get_value("Pick List", pl_name, "work_order")
        if wo_name:
            work_orders.add(wo_name)

    # 1) Recompute Pick List balances/status from DB
    for pl in pick_lists:
        try:
            _update_pick_list_status_from_db(pl)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"C4Factory: recompute_after_stock_entry (Pick List {pl})",
            )

    # 2) Recompute WO material transferred based on all Pick Lists
    for wo in work_orders:
        try:
            _recompute_wo_material_transfer_from_pls(wo)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"C4Factory: recompute_after_stock_entry (WO {wo})",
            )


def recompute_after_stock_entry_links(pick_lists=None, work_orders=None):
    for pl in pick_lists or []:
        if not frappe.db.exists("Pick List", pl):
            continue
        try:
            _update_pick_list_status_from_db(pl)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"C4Factory: recompute_after_stock_entry_links (PL {pl})",
            )

    for wo in work_orders or []:
        if not frappe.db.exists("Work Order", wo):
            continue
        try:
            _recompute_wo_material_transfer_from_pls(wo)
            recompute_work_order_costing(wo)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"C4Factory: recompute_after_stock_entry_links (WO {wo})",
            )

# ---------------------------------------------------------
# Pick List doc events
# ---------------------------------------------------------

def on_pick_list_submit(doc, method: str | None = None):
    """
    Called from hooks on Pick List submit.

    Create operation Job Cards for this Pick List and refresh its status.
    Material transfer is still driven by Stock Entries.
    """
    try:
        _ensure_job_cards_for_pick_list(doc)
        update_pick_list_operation_cost(doc.name)
    except Exception:
        frappe.log_error(
            title="C4Factory: auto Job Card from Pick List failed",
            message=frappe.get_traceback(),
        )

    try:
        _update_pick_list_status_from_db(doc.name)
    except Exception:
        frappe.log_error(
            title="C4Factory: on_pick_list_submit failed",
            message=frappe.get_traceback(),
        )


def _ensure_job_cards_for_pick_list(pl_doc) -> None:
    """
    Create one Job Card per Work Order operation for this Pick List.

    The auto Job Cards are tied to the Pick List through custom_pick_list when
    that custom field exists. They carry the Pick List's production quantity so
    operation cost can be allocated to the same material lot that was picked.
    """
    wo_name = pl_doc.get("work_order")
    if not wo_name:
        return

    wo = frappe.get_doc("Work Order", wo_name)
    operations = wo.get("operations") or []
    if not operations:
        return

    jc_meta = _ensure_job_card_pick_list_meta()
    has_custom_pick_list = jc_meta.has_field("custom_pick_list")
    pick_qty = (
        flt(pl_doc.get("for_qty"))
        or flt(pl_doc.get("custom_for_qty"))
        or flt(pl_doc.get("qty"))
        or 1.0
    )

    for op in operations:
        operation = op.get("operation")
        workstation = op.get("workstation")

        filters = {"work_order": wo.name}
        if has_custom_pick_list:
            filters["custom_pick_list"] = pl_doc.name
        if operation and jc_meta.has_field("operation"):
            filters["operation"] = operation
        if workstation and jc_meta.has_field("workstation"):
            filters["workstation"] = workstation

        if frappe.db.exists("Job Card", filters):
            continue

        jc = frappe.new_doc("Job Card")
        _set_if_field(jc, jc_meta, "work_order", wo.name)
        _set_if_field(jc, jc_meta, "company", wo.get("company"))
        _set_if_field(jc, jc_meta, "bom_no", wo.get("bom_no"))
        _set_if_field(jc, jc_meta, "production_item", wo.get("production_item"))
        _set_if_field(jc, jc_meta, "item_name", wo.get("item_name"))
        _set_if_field(jc, jc_meta, "operation", operation)
        _set_if_field(jc, jc_meta, "workstation", workstation)
        _set_if_field(jc, jc_meta, "for_quantity", pick_qty)
        _set_if_field(jc, jc_meta, "total_completed_qty", pick_qty)
        _set_if_field(jc, jc_meta, "completed_qty", pick_qty)
        _set_if_field(jc, jc_meta, "process_loss_qty", 0)
        _set_if_field(jc, jc_meta, "status", "Completed")
        _set_if_field(jc, jc_meta, "custom_pick_list", pl_doc.name)

        for op_field, jc_field in (
            ("name", "work_order_operation"),
            ("name", "operation_id"),
            ("idx", "sequence_id"),
            ("idx", "operation_row_id"),
            ("time_in_mins", "time_required"),
            ("time_in_mins", "for_time"),
            ("hour_rate", "hour_rate"),
        ):
            _set_if_field(jc, jc_meta, jc_field, op.get(op_field))
        _set_if_field(jc, jc_meta, "operation_row_number", op.name)

        jc.insert(ignore_permissions=True, ignore_mandatory=True)


def _set_if_field(doc, meta, fieldname: str, value) -> None:
    if value is not None and meta.has_field(fieldname):
        doc.set(fieldname, value)


def _ensure_job_card_pick_list_meta():
    meta = frappe.get_meta("Job Card")
    if meta.has_field("custom_pick_list"):
        return meta

    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

        create_custom_fields(
            {
                "Job Card": [
                    {
                        "fieldname": "custom_pick_list",
                        "label": "Pick List (C4)",
                        "fieldtype": "Link",
                        "options": "Pick List",
                        "insert_after": "work_order",
                        "read_only": 1,
                    }
                ]
            },
            update=True,
        )
        frappe.clear_cache(doctype="Job Card")
        meta = frappe.get_meta("Job Card")
    except Exception:
        frappe.log_error(
            title="C4Factory: ensure Job Card custom_pick_list failed",
            message=frappe.get_traceback(),
        )

    return meta


def update_pick_list_operation_cost(pick_list_name: str | None) -> None:
    if not pick_list_name:
        return

    pl_meta = frappe.get_meta("Pick List")
    if not pl_meta.has_field("custom_operation_cost"):
        return

    wo_name = frappe.db.get_value("Pick List", pick_list_name, "work_order")
    if not wo_name:
        return

    from c4factory.c4_manufacturing.stock_entry_hooks import (
        _get_work_order_operating_cost_from_job_cards,
    )

    operation_cost = _get_work_order_operating_cost_from_job_cards(
        wo_name, pick_lists={pick_list_name}
    )

    frappe.db.set_value(
        "Pick List",
        pick_list_name,
        "custom_operation_cost",
        operation_cost,
        update_modified=False,
    )


def on_pick_list_cancel(doc, method: str | None = None):
    """
    Called from hooks on Pick List cancel.

    Same logic as submit: recompute the status based on linked
    Stock Entries (if any).
    """
    wo_name = doc.get("work_order")
    try:
        _update_pick_list_status_from_db(doc.name)
    except Exception:
        frappe.log_error(
            title="C4Factory: on_pick_list_cancel failed",
            message=frappe.get_traceback(),
        )

    if wo_name:
        try:
            _recompute_wo_material_transfer_from_pls(wo_name)
            recompute_work_order_costing(wo_name)
        except Exception:
            frappe.log_error(
                title="C4Factory: on_pick_list_cancel WO recompute failed",
                message=frappe.get_traceback(),
            )


def on_pick_list_trash(doc, method: str | None = None):
    """Refresh Work Order transfer/costing when a canceled Pick List is deleted."""
    wo_name = doc.get("work_order")
    if not wo_name:
        return

    try:
        _recompute_wo_material_transfer_from_pls(wo_name)
        recompute_work_order_costing(wo_name)
    except Exception:
        frappe.log_error(
            title="C4Factory: on_pick_list_trash WO recompute failed",
            message=frappe.get_traceback(),
        )
