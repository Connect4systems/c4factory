# c4napata/api/contract_bom.py
from __future__ import annotations
import frappe
from frappe.model.mapper import get_mapped_doc
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
    def _postprocess(source, target):
        target.sales_order = source.name
        if not target.get("date"):
            target.date = today()

    def _map_item_row(source, target, source_parent=None):
        # Assign every specification from this exact Sales Order Item row.
        # Keeping this explicit prevents values from falling back to another row
        # or relying on automatic same-name field mapping.
        for source_field, target_field in SALES_ORDER_ITEM_SPEC_FIELD_MAP.items():
            target.set(target_field, source.get(source_field))

        # Item Name and Item Image belong to the Item master, not the Sales Order row.
        item_details = frappe.db.get_value(
            "Item",
            source.item_code,
            ["item_name", "image"],
            as_dict=True,
        ) or {}
        target.item_name = item_details.get("item_name")
        target.image = item_details.get("image")

    doc = get_mapped_doc(
        "Sales Order",
        sales_order,
        {
            "Sales Order": {"doctype": "Contract BOM Request"},
            "Sales Order Item": {
                "doctype": "Contract BOM Item",
                "field_map": {
                    "item_code": "item",
                    "description": "description",
                    "qty": "qty",
                    **SALES_ORDER_ITEM_SPEC_FIELD_MAP,
                },
                "postprocess": _map_item_row,
            },
        },
        target_doc=None,
        postprocess=_postprocess,
    )
    return doc
