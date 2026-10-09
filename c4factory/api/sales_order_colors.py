import json

import frappe
from frappe import _


@frappe.whitelist()
def get_color_rows(part_list):
	part = frappe.get_doc("Part List", part_list)
	part.check_permission("read")
	field = "panel_materials" if part.meta.has_field("panel_materials") else "pick_list_materials"
	return [
		{
			"source_row": row.name,
			"material": row.material,
			"part_name": row.part_name,
			"color_doctype": frappe.db.get_value("Part Material", row.material, "color"),
			"color": row.basic_color,
		}
		for row in part.get(field) or [] if row.edite_color
	]


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
			cache[part_list] = get_color_rows(part_list)
		try:
			stored = json.loads(item.get("custom_color_sample_data") or "{}")
			if not isinstance(stored, dict) or not isinstance(stored.get("rows", []), list):
				raise ValueError
		except (ValueError, TypeError):
			frappe.throw(_("Row {0}: Invalid color sample data.").format(item.idx))
		selected = {row.get("source_row"): row for row in stored.get("rows", []) if isinstance(row, dict)}
		rows = []
		for source in cache[part_list]:
			row = dict(source)
			choice = selected.get(row["source_row"], {}) if stored.get("part_list") == part_list else {}
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
		item.custom_color_sample_data = json.dumps({"part_list": part_list, "rows": rows})
