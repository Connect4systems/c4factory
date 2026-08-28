# c4napata/api/contract_bom.py
from __future__ import annotations
import frappe
from frappe.utils import today


SALES_ORDER_ITEM_SPEC_FIELD_MAP = {
    "custom_location_code": "location_code",
    "custom_sub_code": "sub_code",
    "custom_plexi": "plexi",
    "custom_top": "top",
    "custom_modesty": "modesty",
    "custom_wood": "wood",
    "custom_metal": "metal",
    "custom_leather": "leather",
    "custom_drawer_body": "drawer_body",
    "custom_drawer_face": "drawer_face",
    "custom_glass": "glass",
    "custom_fabric": "fabric",
    "custom_direction": "direction",
    "custom_other": "other",
    "additional_notes": "additional_notes",
}


@frappe.whitelist()
def make_contract_bom_request(sales_order: str):
    """
    Build (unsaved) Contract BOM Request from a Sales Order.

    - Sets Contract BOM Request.sales_order = <SO>
    - Copies Sales Order Item details and specifications -> Contract BOM Item
    """
    source = frappe.get_doc("Sales Order", sales_order)
    source.check_permission("read")

    target = frappe.new_doc("Contract BOM Request")
    target.check_permission("create")
    target.sales_order = source.name
    target.customer = source.customer
    target.date = today()

    item_details_cache = {}
    for source_row in sorted(source.items, key=lambda row: row.idx or 0):
        if source_row.item_code not in item_details_cache:
            item_details_cache[source_row.item_code] = frappe.db.get_value(
                "Item",
                source_row.item_code,
                ["item_name", "image"],
                as_dict=True,
            ) or {}

        item_details = item_details_cache[source_row.item_code]
        target_row = {
            "item": source_row.item_code,
            "item_name": item_details.get("item_name"),
            "image": item_details.get("image"),
            "description": source_row.description,
            "qty": source_row.qty,
        }
        for source_field, target_field in SALES_ORDER_ITEM_SPEC_FIELD_MAP.items():
            target_row[target_field] = source_row.get(source_field)

        target.append("items", target_row)

    return target
