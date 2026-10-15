"""Convert legacy per-DocType colors without deleting the legacy catalogs."""
import json

import frappe


def execute():
	mapping = {}
	for material in frappe.get_all("Part Material", fields=["name", "color", "color_palette"]):
		legacy = material.color
		if not legacy or legacy == "Material Color" or not frappe.db.exists("DocType", legacy):
			continue
		palette = material.color_palette or legacy
		if not frappe.db.exists("Color Palette", palette):
			frappe.get_doc({"doctype": "Color Palette", "color_palette": palette}).insert(ignore_permissions=True)
		meta = frappe.get_meta(legacy)
		if meta.istable or meta.issingle:
			frappe.throw("Cannot migrate color catalog " + legacy)
		for record in frappe.get_all(legacy, pluck="name"):
			name = record
			if frappe.db.exists("Material Color", name):
				if frappe.db.get_value("Material Color", name, "palette") != palette:
					name = palette + " - " + record
			if not frappe.db.exists("Material Color", name):
				frappe.get_doc({"doctype": "Material Color", "palette": palette, "color": name}).insert(ignore_permissions=True)
			elif frappe.db.get_value("Material Color", name, "palette") != palette:
				frappe.throw("Conflicting Material Color during migration: " + name)
			mapping[(legacy, record, material.name)] = (palette, name)
		frappe.db.set_value("Part Material", material.name, {"color_palette": palette, "color": None}, update_modified=False)
	for row in frappe.get_all("Part List Materials", fields=["name", "material", "color_doctype", "basic_color", "color_palette"]):
		palette = row.color_palette or frappe.db.get_value("Part Material", row.material, "color_palette")
		color = row.basic_color
		if color and row.color_doctype != "Material Color":
			converted = mapping.get((row.color_doctype, color, row.material))
			if not converted:
				frappe.throw("Cannot migrate color for Part List Materials row " + row.name)
			palette, color = converted
		frappe.db.set_value("Part List Materials", row.name, {"color_palette": palette, "basic_color": color,
			"color_doctype": "Material Color" if palette else None}, update_modified=False)
	for doctype in ("Sales Order Item", "Color Sample Item"):
		if not frappe.get_meta(doctype).has_field("custom_color_sample_data"):
			continue
		for item in frappe.get_all(doctype, fields=["name", "custom_color_sample_data"]):
			if not item.custom_color_sample_data:
				continue
			data = json.loads(item.custom_color_sample_data)
			for row in data.get("rows", []):
				legacy = row.get("color_doctype")
				if legacy == "Material Color":
					continue
				palette = frappe.db.get_value("Part Material", row.get("material"), "color_palette")
				if row.get("color"):
					converted = mapping.get((legacy, row["color"], row.get("material")))
					if not converted:
						frappe.throw("Cannot migrate saved color in " + doctype + " " + item.name)
					palette, row["color"] = converted
				row.update(color_palette=palette, color_doctype="Material Color" if palette else None)
			frappe.db.set_value(doctype, item.name, "custom_color_sample_data", json.dumps(data), update_modified=False)
