import frappe
from frappe import _


def material_table_fields(doc):
	return [field.fieldname for field in doc.meta.fields
		if field.fieldtype == "Table" and field.options == "Part List Materials"]


def validate_material_colors(doc, method=None):
	fields = material_table_fields(doc)
	if not fields:
		return
	previous = doc.get_doc_before_save()
	for field in fields:
		old_rows = {row.name: row for row in previous.get(field) or []} if previous else {}
		for row in doc.get(field) or []:
			target = frappe.db.get_value("Part Material", row.material, "color") if row.material else None
			old_row = old_rows.get(row.name)
			if (old_row and old_row.material != row.material) or row.color_doctype != target or not target:
				row.basic_color = None
			row.color_doctype = target
			if target:
				meta = frappe.get_meta(target)
				if meta.istable or meta.issingle:
					frappe.throw(_("Row {0}: Material Color must reference a regular DocType.").format(row.idx))
			if row.basic_color and not frappe.db.exists(target, row.basic_color):
				frappe.throw(_("Row {0}: Color must be an existing record in {1}.").format(row.idx, target))
