# c4napata/api/contract_bom.py
from __future__ import annotations
import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import today

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

    doc = get_mapped_doc(
        "Sales Order",
        sales_order,
        {
            "Sales Order": {"doctype": "Contract BOM Request"},
            "Sales Order Item": {
                "doctype": "Contract BOM Item",
                "field_map": {
                    "item_code": "item",
                    "item_name": "item_name",
                    "description": "description",
                    "qty": "qty",
                    "image": "image",
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
                },
            },
        },
        target_doc=None,
        postprocess=_postprocess,
    )
    return doc
