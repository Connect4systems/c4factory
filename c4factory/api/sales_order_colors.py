import json

import frappe
from frappe import _

from c4factory.api.part_list_material_colors import material_color_target, material_table_fields, material_palette, validate_palette_color


@frappe.whitelist()
def get_color_rows(part_list):
	part = frappe.get_doc("Part List", part_list)
	part.check_permission("read")
	return [
		{
			"source_row": row.name,
			"material": row.material,
			"part_name": row.part_name,
			"color_doctype": material_color_target(part, field, row),
			"color_palette": material_palette(row),
			"color": row.basic_color,
		}
		for field in material_table_fields(part)
		for row in part.get(field) or [] if row.edite_color
	]


@frappe.whitelist()
def get_part_list_colors(part_list):
	part = frappe.get_doc("Part List", part_list)
	part.check_permission("read")
	return {
		"rows": [
			{
				"source_row": row.name, "source_table": field,
				"material": row.material, "part_name": row.part_name,
				"color_doctype": material_color_target(part, field, row),
				"color_palette": material_palette(row),
				"color": row.basic_color, "has_source_color": bool(row.basic_color), "edite_color": row.edite_color,
			}
			for field in ("panel_materials", "metal_material", "other_material")
			for row in part.get(field) or [] if row.basic_color or row.edite_color
		],
	}


def validate_colors(doc, method=None):
	cache = {}
	for item in doc.items:
		if not item.meta.has_field("custom_color_sample_data"):
			continue
		part_list = item.get("custom_part_list") or item.get("part_list")
		if not part_list:
			item.custom_color_sample_data = None
			continue
		if part_list not in cache:
			cache[part_list] = get_part_list_colors(part_list)
		config = cache[part_list]
		try:
			stored = json.loads(item.get("custom_color_sample_data") or "{}")
			if not isinstance(stored, dict) or not isinstance(stored.get("rows", []), list):
				raise ValueError
		except (ValueError, TypeError):
			frappe.throw(_("Row {0}: Invalid color sample data.").format(item.idx))
		matching = stored.get("part_list") == part_list
		selected = {row.get("source_row"): row for row in stored.get("rows", []) if isinstance(row, dict)}
		rows = []
		for source in config["rows"]:
			row = dict(source)
			choice = selected.get(row["source_row"], {}) if matching else {}
			target = row["color_doctype"]
			if choice.get("color_doctype") == target and choice.get("color_palette") == row.get("color_palette"):
				row["color"] = choice.get("color")
			if not target:
				row["color"] = None
			validate_palette_color(row.get("color_palette"), row["color"])
			rows.append(row)
		item.custom_color_sample_data = json.dumps({"part_list": part_list, "rows": rows})
