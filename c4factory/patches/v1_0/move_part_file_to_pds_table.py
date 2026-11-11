"""Preserve legacy workbook attachments in the existing PDS child table."""
import frappe


def execute():
    # Some sites customized the Title label to Customer.
    for setter in frappe.get_all("Property Setter", filters={
        "doc_type": "PDS Table", "field_name": "title", "property": "label",
    }, pluck="name"):
        frappe.db.set_value("Property Setter", setter, "value", "Title")
    frappe.clear_cache(doctype="PDS Table")

    if not frappe.db.has_column("Part List", "part_file"):
        return
    for part in frappe.get_all("Part List", filters={"part_file": ["!=", ""]},
                               fields=["name", "part_file", "docstatus"]):
        if not frappe.db.exists("PDS Table", {
            "parent": part.name, "parenttype": "Part List",
            "parentfield": "pds_table", "arttach": part.part_file,
        }):
            index = frappe.db.sql("""select coalesce(max(idx), 0) from `tabPDS Table`
                where parent=%s and parenttype='Part List' and parentfield='pds_table'""",
                                  (part.name,))[0][0]
            frappe.get_doc({
                "doctype": "PDS Table", "parent": part.name,
                "parenttype": "Part List", "parentfield": "pds_table",
                "idx": index + 1, "docstatus": part.docstatus,
                "title": "Part File", "arttach": part.part_file,
            }).db_insert()
        frappe.db.set_value("Part List", part.name, "part_file", None, update_modified=False)
        for file_name in frappe.get_all("File", filters={
            "attached_to_doctype": "Part List", "attached_to_name": part.name,
            "file_url": part.part_file, "attached_to_field": "part_file",
        }, pluck="name"):
            frappe.db.set_value("File", file_name, "attached_to_field", "pds_table", update_modified=False)
