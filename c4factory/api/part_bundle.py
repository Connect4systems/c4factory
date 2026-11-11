import math

import frappe
from frappe import _


BUNDLE_TABLES = {
    "panel_materials": "Part List Materials",
    "metal_material": "Part List Materials",
    "other_material": "Part List Materials",
    "accessorise_table": "Accessorise Table",
}


@frappe.whitelist()
def get_bundle_rows(part_bundle, qty=1):
    """Return a permitted bundle's data rows, without child document identities."""
    try:
        multiplier = float(qty)
    except (TypeError, ValueError):
        multiplier = 0
    if not math.isfinite(multiplier) or multiplier <= 0:
        frappe.throw(_("Quantity must be a positive number."))

    bundle = frappe.get_doc("Part Bundle", part_bundle)
    bundle.check_permission("read")
    result = {}
    for table, child_type in BUNDLE_TABLES.items():
        fields = frappe.get_meta(child_type).get_valid_columns()
        # Only copy declared data fields, never names, parent links or audit fields.
        fields = [field.fieldname for field in frappe.get_meta(child_type).fields
                  if field.fieldname in fields and not getattr(field, "no_copy", False)]
        result[table] = []
        for row in bundle.get(table) or []:
            values = {field: row.get(field) for field in fields}
            quantity = float(row.get("qty") or 0) * multiplier
            if not math.isfinite(quantity):
                frappe.throw(_("Bundle row quantities must be finite numbers."))
            values["qty"] = quantity
            result[table].append(values)
    return result
