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
			"material": material_palette(row) or row.get("material"),
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
		"base_colors": [
			{"source_table": field, "color_palette": part.get(prefix + "_color_palette"),
			 "color": part.get(prefix + "_base_color"), "allow_edit": bool(part.get(prefix + "_allow_edit"))}
			for prefix, field in (("panel", "panel_materials"), ("metal", "metal_material"), ("other", "other_material"))
		],
		"rows": [
			{
				"source_row": row.name, "source_table": field,
				"material": material_palette(row) or row.get("material"), "part_name": row.part_name,
				"color_doctype": material_color_target(part, field, row),
				"color_palette": material_palette(row),
				"color": row.basic_color, "has_source_color": bool(row.basic_color), "edite_color": row.edite_color,
			}
			for field in ("panel_materials", "metal_material", "other_material")
			for row in part.get(field) or []
		],
	}


def sample_base_colors(config, stored):
	"""Use current Technical permissions; never trust flags sent by a client."""
	choices = stored.get("base_colors", [])
	if not isinstance(choices, list):
		frappe.throw(_("Invalid base color data."))
	selected = {row.get("source_table"): row for row in choices if isinstance(row, dict)}
	result = []
	for source in config.get("base_colors", []):
		base = dict(source)
		choice = selected.get(base["source_table"])
		if choice and choice.get("color_palette") == base.get("color_palette"):
			color = choice.get("color")
			if (color or "") != (base.get("color") or "") and not base["allow_edit"]:
				frappe.throw(_("Base color editing is not enabled for {0}.").format(base["source_table"]))
			base["color"] = color
		validate_palette_color(base.get("color_palette"), base.get("color"))
		result.append(base)
	return result


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
		is_sample = item.get("doctype") == "Color Sample Item"
		bases = sample_base_colors(config, stored if matching else {}) if is_sample else config.get("base_colors", [])
		base_by_table = {base["source_table"]: base for base in bases}
		defaults = {base["source_table"]: base for base in config.get("base_colors", [])}
		selected = {row.get("source_row"): row for row in stored.get("rows", []) if isinstance(row, dict)}
		rows = []
		for source in config["rows"]:
			row = dict(source)
			choice = selected.get(row["source_row"], {}) if matching else {}
			target = row["color_doctype"]
			base = base_by_table.get(row.get("source_table"))
			base_changed = is_sample and base and base.get("color") != defaults[base["source_table"]].get("color")
			if base_changed and row.get("color_palette") == base.get("color_palette"):
				row["color"] = base.get("color")
			if choice.get("color_doctype") == target and choice.get("color_palette") == row.get("color_palette"):
				if not base_changed or row.get("edite_color"):
					row["color"] = choice.get("color")
			if not target:
				row["color"] = None
			validate_palette_color(row.get("color_palette"), row["color"])
			rows.append(row)
		item.custom_color_sample_data = json.dumps({"part_list": part_list, "base_colors": bases, "rows": rows})
