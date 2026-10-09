# Copyright (c) 2026, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PartList(Document):
	def before_validate(self):
		wood_type = self.get("wood_type") or "Artificial Wood"
		target = {"Artificial Wood": "P-Wood", "Natural Wood": "P-Natural"}.get(wood_type)
		if not target:
			frappe.throw(_("Wood Type must be Artificial Wood or Natural Wood."))
		previous = self.get_doc_before_save()
		if (
			(previous and (previous.get("wood_type") or "Artificial Wood") != wood_type)
			or (self.get("wood_color_doctype") and self.wood_color_doctype != target)
		):
			self.wood_color = None
		self.wood_type = wood_type
		self.wood_color_doctype = target
		if self.get("wood_color") and not frappe.db.exists(target, self.wood_color):
			frappe.throw(_("Wood Color must be an existing record in {0}.").format(target))

	def on_submit(self):
		from c4factory.api.pds_request import update_sales_order_part_list

		update_sales_order_part_list(self)
