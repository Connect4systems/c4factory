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


def validate_material_colors(doc, method=None):
	# Production Orders retain the approved sample's colors as a snapshot.
	if doc.doctype == "Production Order":
		return
	previous = doc.get_doc_before_save()
	for field in material_table_fields(doc):
		old_rows = {row.name: row for row in previous.get(field) or []} if previous else {}
		for row in doc.get(field) or []:
			old = old_rows.get(row.name)
			if old and old.material != row.material:
				row.color_palette = frappe.db.get_value("Part Material", row.material, "color_palette") if row.material else None
				row.basic_color = None
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
	return frappe.get_list("Material Color", filters={"palette": palette},
		or_filters={"name": ["like", "%" + txt + "%"], "color": ["like", "%" + txt + "%"]},
		fields=["name", "color"], order_by="name", start=start, page_length=page_len, as_list=True)
