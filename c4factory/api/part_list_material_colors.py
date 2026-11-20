import frappe
from frappe import _


def material_table_fields(doc):
	return [field.fieldname for field in doc.meta.fields
		if field.fieldtype == "Table" and field.options == "Part List Materials"]


def material_palette(row):
	return row.get("color_palette") or (frappe.db.get_value("Part Material", row.material, "color_palette") if row.material else None)


def material_color_target(doc, field, row):
	return "Material Color" if material_palette(row) else None


def validate_palette_color(palette, color):
	if color and (not palette or not frappe.db.exists("Material Color", {"name": color, "palette": palette})):
		frappe.throw(_("Color {0} must belong to Color Palette {1}.").format(color, palette or ""))
	if color and frappe.db.get_value("Material Color", color, "disable"):
		frappe.throw(_("Material Color {0} is disabled. Select an enabled color.").format(color))


def validate_material_colors(doc, method=None):
	# Production Orders retain the approved sample's colors as a snapshot.
	if doc.doctype == "Production Order":
		return
	previous = doc.get_doc_before_save()
	for field in material_table_fields(doc):
		prefix = {"panel_materials": "panel", "metal_material": "metal", "other_material": "other"}.get(field) if doc.doctype == "Part List" else None
		palette = doc.get(prefix + "_color_palette") if prefix else None
		base = doc.get(prefix + "_base_color") if prefix else None
		palette_changed = bool(prefix and previous and palette != previous.get(prefix + "_color_palette"))
		if palette_changed and base == previous.get(prefix + "_base_color"):
			base = None
			setattr(doc, prefix + "_base_color", None)
		base_changed = bool(prefix and previous and base != previous.get(prefix + "_base_color") and (not palette_changed or base))
		if prefix:
			validate_palette_color(palette, base)
		old_rows = {row.name: row for row in previous.get(field) or []} if previous else {}
		for row in doc.get(field) or []:
			old = old_rows.get(row.name)
			if old and old.material != row.material:
				row.color_palette = frappe.db.get_value("Part Material", row.material, "color_palette") if row.material else None
				row.basic_color = None
			if palette or palette_changed:
				row.color_palette = palette
				if palette_changed and row.basic_color and not frappe.db.exists("Material Color", {"name": row.basic_color, "palette": palette}):
					row.basic_color = None
			if base_changed or (base and not old and not row.basic_color):
				row.basic_color = base
			if not prefix or (not palette and not palette_changed):
				row.color_palette = material_palette(row)
			row.color_doctype = "Material Color" if row.color_palette else None
			validate_palette_color(row.color_palette, row.basic_color)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def material_color_query(doctype, txt, searchfield, start, page_len, filters):
	"""Search only the new catalog; never interpret a material as a DocType."""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	palette = filters.get("palette")
	if not palette and filters.get("material"):
		palette = frappe.db.get_value("Part Material", filters["material"], "color_palette")
	if not palette:
		return []
	return frappe.get_list("Material Color", filters={"palette": palette, "disable": 0},
		or_filters={"name": ["like", "%" + txt + "%"]},
		fields=["name"], order_by="name", start=start, page_length=page_len, as_list=True)
