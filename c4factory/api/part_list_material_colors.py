import frappe
from frappe import _


def material_table_fields(doc):
	return [field.fieldname for field in doc.meta.fields
		if field.fieldtype == "Table" and field.options == "Part List Materials"]


def material_color_target(doc, field, row):
	if doc.doctype == "Part List":
		if field == "panel_materials":
			return {"Artificial Wood": "P-Wood", "Natural Wood": "P-Natural"}.get(
				doc.get("wood_type") or "Artificial Wood")
		if field == "metal_material":
			return "P-Metal"
	return frappe.db.get_value("Part Material", row.material, "color") if row.material else None


def validate_material_colors(doc, method=None):
	fields = material_table_fields(doc)
	if not fields:
		return
	previous = doc.get_doc_before_save()
	for field in fields:
		old_rows = {row.name: row for row in previous.get(field) or []} if previous else {}
		for row in doc.get(field) or []:
			target = material_color_target(doc, field, row)
			old_row = old_rows.get(row.name)
			header_color = doc.doctype == "Part List" and field in ("panel_materials", "metal_material")
			if (not header_color and old_row and old_row.material != row.material) or row.color_doctype != target or not target:
				row.basic_color = None
			row.color_doctype = target
			if doc.doctype == "Part List" and not old_row and not row.basic_color:
				default_field = {"panel_materials": "wood_color", "metal_material": "metal_color"}.get(field)
				if default_field:
					row.basic_color = doc.get(default_field)
			if target:
				meta = frappe.get_meta(target)
				if meta.istable or meta.issingle:
					frappe.throw(_("Row {0}: Material Color must reference a regular DocType.").format(row.idx))
			if row.basic_color and not frappe.db.exists(target, row.basic_color):
				frappe.throw(_("Row {0}: Color must be an existing record in {1}.").format(row.idx, target))
