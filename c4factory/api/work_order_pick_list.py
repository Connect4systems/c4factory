from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from c4factory.c4_manufacturing.work_order_hooks import get_default_source_warehouse


def _resolve_work_order_arg(
    work_order: str | None = None,
    source_name: str | None = None,
    work_order_id: str | None = None,
    name: str | None = None,
    **extras,
) -> str:
    doc = extras.get("doc")
    if isinstance(doc, dict):
        name = name or doc.get("name")

    return (work_order or source_name or work_order_id or name or "").strip()


def _get_component_rows(wo):
    return wo.get("required_items") or wo.get("items") or []


@frappe.whitelist()
def create_pick_list(
    work_order: str | None = None,
    source_name: str | None = None,
    for_qty: float | None = None,
    **kwargs,
):
    """
    Create Pick List from Work Order required items and C4 default warehouses.
    """
    wo_name = _resolve_work_order_arg(
        work_order=work_order,
        source_name=source_name,
        **kwargs,
    )
    if not wo_name:
        frappe.throw(_("Work Order is required."))

    wo = frappe.get_doc("Work Order", wo_name)
    if wo.docstatus != 1:
        frappe.throw(_("Work Order must be submitted before creating a Pick List."))

    rows = _get_component_rows(wo)
    if not rows:
        frappe.throw(_("Work Order has no required items."))

    fg_qty = flt(for_qty) or max(flt(wo.qty) - flt(wo.produced_qty), 0.0)
    if fg_qty <= 0:
        frappe.throw(_("No remaining quantity to pick for Work Order {0}.").format(wo.name))

    qty_scale = fg_qty / (flt(wo.qty) or 1.0)

    pl = frappe.new_doc("Pick List")
    pl.company = wo.company
    pl.purpose = "Material Transfer for Manufacture"
    pl.work_order = wo.name

    for fieldname in ("for_qty", "qty_of_finished_goods", "qty_of_finished_goods_item"):
        if hasattr(pl, fieldname):
            pl.set(fieldname, fg_qty)

    count = 0
    for wo_item in rows:
        item_code = wo_item.get("item_code")
        if not item_code:
            continue

        required_qty = flt(wo_item.get("required_qty") or wo_item.get("qty"))
        row_qty = required_qty * qty_scale
        if row_qty <= 0:
            continue

        warehouse = _get_pick_list_source_warehouse(wo, wo_item)
        if not warehouse:
            frappe.throw(_("Source Warehouse is required for item {0}.").format(item_code))

        stock_uom = (
            wo_item.get("stock_uom")
            or wo_item.get("uom")
            or frappe.db.get_value("Item", item_code, "stock_uom")
        )
        item_name = (
            wo_item.get("item_name")
            or frappe.db.get_value("Item", item_code, "item_name")
            or item_code
        )

        pl_row = pl.append(
            "locations",
            {
                "item_code": item_code,
                "item": item_code,
                "item_name": item_name,
                "uom": stock_uom,
                "stock_uom": stock_uom,
                "conversion_factor": 1,
                "qty": row_qty,
                "stock_qty": row_qty,
                "qty_in_stock_uom": row_qty,
                "warehouse": warehouse,
                "work_order": wo.name,
            },
        )
        _set_if_present(pl_row, "custom_pl_qty", row_qty)
        _set_if_present(pl_row, "custom_work_order_item", wo_item.name)
        _set_if_present(pl_row, "custom_wip_warehouse", wo.get("wip_warehouse"))
        count += 1

    if count == 0:
        frappe.throw(_("No valid required items to pick for Work Order {0}.").format(wo.name))

    return pl.as_dict()


def _get_pick_list_source_warehouse(wo, wo_item) -> str | None:
    item_code = wo_item.get("item_code")
    item_group = wo_item.get("item_group")
    if not item_group and item_code:
        item_group = frappe.db.get_value("Item", item_code, "item_group")

    return (
        get_default_source_warehouse(
            item_code=item_code,
            item_group=item_group,
            company=wo.get("company"),
        )
        or wo_item.get("source_warehouse")
        or wo_item.get("from_warehouse")
        or wo.get("source_warehouse")
    )


def _set_if_present(doc, fieldname: str, value) -> None:
    if hasattr(doc, fieldname):
        doc.set(fieldname, value)
