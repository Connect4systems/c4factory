"""Copy quotation details once, preserving subsequent user edits."""
import frappe


def source_field(doctype, label, candidates):
    meta = frappe.get_meta(doctype)
    labelled = next((f.fieldname for f in meta.fields if (f.label or "").strip().lower() == label.lower()), None)
    return labelled or next((name for name in candidates if meta.has_field(name)), None)


def fill_sales_order(doc, method=None):
    title_field = source_field("Quotation", "Project Title", ("custom_project_title", "project_title"))
    note_field = source_field("Quotation Item", "Note", ("custom_note", "note", "additional_notes", "custom_additional_notes"))
    titles = set()
    for row in doc.items:
        quotation = row.get("prevdoc_docname")
        source = None
        if row.get("quotation_item"):
            source = frappe.db.get_value("Quotation Item", row.quotation_item,
                ["parent", "item_code"] + ([note_field] if note_field else []), as_dict=True)
            # Match the source row, never a different row sharing an item code.
            if source and source.item_code == row.item_code and (not quotation or source.parent == quotation):
                quotation = source.parent
            else:
                source = None
        if quotation and title_field:
            title = frappe.db.get_value("Quotation", quotation, title_field)
            if title:
                titles.add(title)
        if not row.get("custom_note_initialized") and source and note_field:
            if row.get("custom_note") is None or row.get("custom_note") == "":
                row.custom_note = source.get(note_field)
            row.custom_note_initialized = 1
    # Combined quotations with conflicting titles need an explicit user choice.
    if not doc.get("custom_project_title") and len(titles) == 1:
        doc.custom_project_title = titles.pop()
