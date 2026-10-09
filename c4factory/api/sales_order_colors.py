import json

import frappe
from frappe import _

from c4factory.api.part_list_material_colors import material_color_target, material_table_fields


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
			"color": row.basic_color,
		}
		for field in material_table_fields(part)
		for row in part.get(field) or [] if row.edite_color
	]


@frappe.whitelist()
def get_part_list_colors(part_list):
	part = frappe.get_doc("Part List", part_list)
	part.check_permission("read")
	wood_target = {"Artificial Wood": "P-Wood", "Natural Wood": "P-Natural"}.get(
		part.get("wood_type") or "Artificial Wood", "P-Wood")
	return {
		"wood_color": part.get("wood_color"),
		"wood_color_doctype": wood_target,
		"metal_color": part.get("metal_color"),
		"rows": [
			{
				"source_row": row.name, "source_table": field,
				"material": row.material, "part_name": row.part_name,
				"color_doctype": material_color_target(part, field, row),
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
			item.custom_wood = None
			item.custom_metal = None
			item.custom_wood_color_doctype = None
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
		if not matching or not item.get("custom_wood_color_doctype"):
			item.custom_wood = config["wood_color"]
			item.custom_metal = config["metal_color"]
		elif item.get("custom_wood_color_doctype") and item.custom_wood_color_doctype != config["wood_color_doctype"]:
			item.custom_wood = config["wood_color"]
		if matching and not stored.get("headers_initialized"):
			if not item.get("custom_wood"):
				item.custom_wood = config["wood_color"]
			if not item.get("custom_metal"):
				item.custom_metal = config["metal_color"]
		item.custom_wood_color_doctype = config["wood_color_doctype"]
		for value, target in ((item.get("custom_wood"), config["wood_color_doctype"]), (item.get("custom_metal"), "P-Metal")):
			if value and not frappe.db.exists(target, value):
				frappe.throw(_("Row {0}: Color must be an existing record in {1}.").format(item.idx, target))
		selected = {row.get("source_row"): row for row in stored.get("rows", []) if isinstance(row, dict)}
		rows = []
		for source in config["rows"]:
			row = dict(source)
			choice = selected.get(row["source_row"], {}) if matching else {}
			target = row["color_doctype"]
			if choice.get("color_doctype") == target:
				row["color"] = choice.get("color")
			if not target:
				row["color"] = None
			elif frappe.get_meta(target).istable or frappe.get_meta(target).issingle:
				frappe.throw(_("Material Color must reference a regular DocType."))
			if row["color"] and not frappe.db.exists(target, row["color"]):
				frappe.throw(_("Row {0}: Color must be an existing record in {1}.").format(item.idx, target))
			rows.append(row)
		item.custom_color_sample_data = json.dumps({"part_list": part_list, "headers_initialized": True, "rows": rows})
