"""Carry sales order details onto delivery notes without replacing edited notes."""
import frappe


def fill_delivery_note(doc, method=None):
    orders = {}
    for row in doc.items:
        order = row.get("against_sales_order")
        if order and order not in orders:
            orders[order] = frappe.db.get_value("Sales Order", order,
                ["custom_project_title", "custom_technical_team"], as_dict=True) or {}
        if not row.get("so_detail") or row.get("custom_note_initialized"):
            continue
        source = frappe.db.get_value("Sales Order Item", row.so_detail,
            ["parent", "item_code", "custom_note"], as_dict=True)
        if not source or source.parent != order or source.item_code != row.item_code:
            continue
        if not row.get("custom_note"):
            row.custom_note = source.get("custom_note")
        row.custom_note_initialized = 1
    for field in ("custom_project_title", "custom_technical_team"):
        values = {source.get(field) or "" for source in orders.values()}
        if not doc.get(field) and len(values) == 1:
            doc.set(field, values.pop())
    # A Project action supplies the header link; ordinary order mappings may
    # supply it only on the items. Never choose one of several projects.
    projects = {row.get("project") for row in doc.items if row.get("project")}
    if doc.get("project"):
        projects = {doc.project}
    if len(projects) == 1:
        project = next(iter(projects))
        doc.custom_project_no = frappe.db.get_value("Project", project, "custom_project_no") or ""
    else:
        doc.custom_project_no = ""
