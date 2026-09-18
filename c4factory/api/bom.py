from frappe.utils import flt


def calculate_item_qty(doc, method=None):
    """Calculate material quantities before BOM validation and costing."""
    for row in doc.get("items") or []:
        qty = 1
        for field in ("custom_unit_qty", "custom_width", "custom_height", "custom_depth"):
            value = row.get(field)
            if value is None or value == "":
                value = 1
                row.set(field, value)
            qty *= flt(value)
        row.qty = flt(qty, row.precision("qty"))
