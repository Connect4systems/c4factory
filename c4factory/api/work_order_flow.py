from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


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
    # using custom_pick_list_item field
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
            result[pl_item_name]["balance"] = max(
                result[pl_item_name]["pl_qty"] - transferred, 0.0
            )

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
    Placeholder validate hook for Pick List.

    Currently it does nothing and just allows save/submit.
    We keep it so that hooks.py can safely call it without errors.
    Later we can add extra validation logic here if needed.
    """
    # no special validation required for now
    return


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


def on_stock_entry_cancel(doc, method=None):
    """
    Hook: Stock Entry.on_cancel

    Same as on_submit: only recompute related docs, never modify SE itself.
    """
    pl_name = doc.get("pick_list")
    if pl_name:
        try:
            _update_pick_list_status_from_db(pl_name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "C4Factory: on_stock_entry_cancel (Pick List)"
            )

    wo_name = doc.get("work_order")
    if wo_name:
        try:
            _recompute_wo_material_transfer_from_pls(wo_name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), "C4Factory: on_stock_entry_cancel (WO)"
            )

from c4factory.c4_manufacturing.stock_entry_hooks import recompute_work_order_costing

def on_stock_entry_cancel(doc, method=None):
    # your existing logic that recalculates balances etc...

    if doc.work_order:
        recompute_work_order_costing(doc.work_order)

# ================================================================
# Recompute Work Order.material_transferred_for_manufacturing
# ================================================================


def _recompute_wo_material_transfer_from_pls(wo_name: str):
    """
    Recompute Work Order.material_transferred_for_manufacturing from all
    submitted Pick Lists linked to this Work Order (sum of for_qty).
    """
    if not wo_name:
        return

    wo = frappe.get_doc("Work Order", wo_name)

    total_for_qty = frappe.db.sql(
        """
        SELECT COALESCE(SUM(for_qty), 0)
        FROM `tabPick List`
        WHERE docstatus = 1
          AND work_order = %(wo)s
        """,
        {"wo": wo_name},
    )[0][0]

    total_for_qty = min(flt(total_for_qty), flt(wo.qty))

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

# ================================================================
# Stock Entry hooks: keep Pick List + Work Order in sync on cancel
# ================================================================


def on_stock_entry_cancel(doc, method=None):
    """
    Stock Entry.on_cancel hook.

    When a Material Transfer for Manufacture Stock Entry that was
    created from a Pick List is cancelled, we want to recalculate:
      - Pick List picked / balance quantities and status
      - Work Order.material_transferred_for_manufacturing

    To avoid transaction-timing issues, we enqueue a background job
    that runs after the Stock Entry is fully cancelled and committed.
    """
    try:
        frappe.enqueue(
            "c4factory.api.work_order_flow.recompute_after_stock_entry",
            se_name=doc.name,
            queue="short",
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), "C4Factory: on_stock_entry_cancel enqueue failed"
        )


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

# ---------------------------------------------------------
# Pick List doc events
# ---------------------------------------------------------

def on_pick_list_submit(doc, method: str | None = None):
    """
    Called from hooks on Pick List submit.

    We only recompute the Pick List status and its balance view.
    Work Order material transfer is driven by Stock Entries.
    """
    try:
        _update_pick_list_status_from_db(doc.name)
    except Exception:
        frappe.log_error(
            title="C4Factory: on_pick_list_submit failed",
            message=frappe.get_traceback(),
        )


def on_pick_list_cancel(doc, method: str | None = None):
    """
    Called from hooks on Pick List cancel.

    Same logic as submit: recompute the status based on linked
    Stock Entries (if any).
    """
    try:
        _update_pick_list_status_from_db(doc.name)
    except Exception:
        frappe.log_error(
            title="C4Factory: on_pick_list_cancel failed",
            message=frappe.get_traceback(),
        )
