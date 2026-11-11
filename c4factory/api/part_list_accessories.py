"""Accessory requirements remain immutable while stock staff resolve Item codes."""
import json
import math

import frappe
from frappe import _
from frappe.utils import now_datetime

MAPPING_FIELDS = {"item", "description", "requested_uom", "conversion_factor", "stock_uom", "stock_qty", "mapping_status", "mapped_by", "mapped_on"}
TECHNICAL_FIELDS = ("product", "product_name", "description", "width", "hight", "depth", "material_line", "metal_material_line")


def stock_user():
    return bool(set(frappe.get_roles()) & {"Stock User", "Stock Manager", "System Manager"})


def positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0
    if not math.isfinite(number) or number <= 0:
        frappe.throw(_("Quantity and conversion factor must be positive finite numbers."))
    return number


def row_values(row, excluded=()):
    return {f.fieldname: row.get(f.fieldname) for f in row.meta.fields
        if f.fieldtype not in {"Section Break", "Column Break", "Tab Break"} and f.fieldname not in excluded}


def require_mapped(doc):
    pending = [str(row.idx) for row in doc.get("accessorise_table") or [] if not row.get("item")]
    if pending:
        frappe.throw(_("Map accessory rows {0} to stock items before creating or submitting a Production Order.").format(", ".join(pending)))


def validate_requirements(doc):
    previous = doc.get_doc_before_save()
    for table in ("panel_materials", "metal_material", "other_material"):
        old_names = {r.name for r in previous.get(table) or []} if previous else set()
        for row in doc.get(table) or []:
            # Existing records remain editable without forcing a translation migration.
            if row.name not in old_names and (not str(row.get("part_name") or "").strip() or not str(row.get("part_name_ar") or "").strip()):
                frappe.throw(_("Row {0}: English and Arabic part names are required.").format(row.idx))
            positive(row.get("qty"))
            for field in ("lenght", "width", "hight", "thickness"):
                value = row.get(field)
                if value is not None:
                    try:
                        valid = math.isfinite(float(value)) and float(value) >= 0
                    except (ValueError, TypeError):
                        valid = False
                    if not valid:
                        frappe.throw(_("Row {0}: dimensions must be non-negative finite numbers.").format(row.idx))
    old = {r.name: r for r in previous.get("accessorise_table") or []} if previous else {}
    for row in doc.get("accessorise_table") or []:
        quantity = positive(row.get("qty"))
        if not str(row.get("requested_name") or "").strip() and not row.get("item"):
            frappe.throw(_("Accessory row {0}: enter a requested name or select an Item.").format(row.idx))
        if not row.get("item"):
            for field in MAPPING_FIELDS:
                row.set(field, "Pending" if field == "mapping_status" else None)
            continue
        item = frappe.get_doc("Item", row.item)
        item.check_permission("read")
        if item.disabled or not item.is_stock_item or item.has_variants:
            frappe.throw(_("Select an enabled stock Item without variants."))
        row.stock_uom = item.stock_uom
        row.requested_uom = row.get("requested_uom") or item.stock_uom
        raw_factor = row.get("conversion_factor")
        factor = positive(1 if raw_factor is None or raw_factor == "" else raw_factor)
        expected = 1 if row.requested_uom == item.stock_uom else next(
            (u.conversion_factor for u in item.get("uoms") or [] if u.uom == row.requested_uom), None)
        if expected is None or not math.isclose(factor, float(expected), rel_tol=1e-9):
            frappe.throw(_("Accessory row {0}: conversion must match the Item UOM conversion.").format(row.idx))
        row.conversion_factor = factor
        row.stock_qty = positive(quantity * factor)
        if frappe.db.get_value("UOM", item.stock_uom, "must_be_whole_number") and not row.stock_qty.is_integer():
            frappe.throw(_("Stock quantity must be a whole number."))
        row.description = item.description
        row.mapping_status = "Matched"
        before = old.get(row.name)
        changed = not before or any(row.get(f) != before.get(f) for f in ("item", "requested_uom", "conversion_factor"))
        row.mapped_by = frappe.session.user if changed else before.get("mapped_by")
        row.mapped_on = now_datetime() if changed else before.get("mapped_on")


def validate_submitted_update(doc):
    previous = doc.get_doc_before_save()
    if not previous:
        frappe.throw(_("Cannot update a submitted Part List without its saved version."))
    for field in TECHNICAL_FIELDS:
        if doc.get(field) != previous.get(field):
            frappe.throw(_("Submitted technical details are locked. Create a new version."))
    for table in ("pds_table", "panel_materials", "metal_material", "other_material"):
        if [row_values(r) for r in doc.get(table) or []] != [row_values(r) for r in previous.get(table) or []]:
            frappe.throw(_("Submitted technical rows are locked. Create a new version."))
    current, old = doc.get("accessorise_table") or [], previous.get("accessorise_table") or []
    if [r.name for r in current] != [r.name for r in old]:
        frappe.throw(_("Submitted accessory rows cannot be added, removed or reordered."))
    changed = False
    for row, before in zip(current, old):
        if row_values(row, MAPPING_FIELDS) != row_values(before, MAPPING_FIELDS):
            frappe.throw(_("Submitted accessory names, notes and requested quantities are locked."))
        changed |= any(row.get(f) != before.get(f) for f in MAPPING_FIELDS)
    if changed:
        if not stock_user():
            frappe.throw(_("Only stock staff may map submitted accessories."), frappe.PermissionError)
        frappe.db.sql("select name from `tabPart List` where name = %s for update", (doc.name,))
        if frappe.db.exists("Production Order", {"part_list": doc.name, "docstatus": ["!=", 2]}):
            frappe.throw(_("This Part List already has Production Orders. Create a new version to change accessory mappings."))
    # Normalize derived values and audit fields even for direct API saves.
    validate_requirements(doc)


@frappe.whitelist()
def map_accessories(part_list, mappings, modified):
    if not stock_user():
        frappe.throw(_("Only stock staff may map submitted accessories."), frappe.PermissionError)
    frappe.db.sql("select name from `tabPart List` where name = %s for update", (part_list,))
    doc = frappe.get_doc("Part List", part_list)
    doc.check_permission("read")
    if doc.docstatus != 1 or str(doc.modified) != str(modified):
        frappe.throw(_("Reload the submitted Part List before mapping accessories."))
    mappings = json.loads(mappings) if isinstance(mappings, str) else mappings
    if not isinstance(mappings, list):
        frappe.throw(_("Invalid accessory mappings."))
    rows = {r.name: r for r in doc.get("accessorise_table") or []}
    seen = set()
    for mapping in mappings:
        if not isinstance(mapping, dict) or mapping.get("row") not in rows or mapping["row"] in seen:
            frappe.throw(_("Invalid or repeated accessory row."))
        seen.add(mapping["row"])
        row = rows[mapping["row"]]
        row.item = mapping.get("item") or None
        row.requested_uom = mapping.get("requested_uom") or None
        row.conversion_factor = mapping.get("conversion_factor", 1)
    # Stock roles only have read permission on the parent. The dedicated operation
    # sets a strict whitelist of fields; controller validation guards all other edits.
    doc.save(ignore_permissions=True)
    return {"matched": sum(bool(r.item) for r in rows.values()), "total": len(rows)}
