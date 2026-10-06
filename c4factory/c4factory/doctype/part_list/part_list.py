# Copyright (c) 2026, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PartList(Document):
	def before_validate(self):
		previous = self.get_doc_before_save()
		table_field = "panel_materials" if self.meta.has_field("panel_materials") else "pick_list_materials"
		old_rows = {row.name: row for row in (previous.get(table_field) or [])} if previous else {}
		for row in self.get(table_field) or []:
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
