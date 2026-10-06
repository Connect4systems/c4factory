# Copyright (c) 2026, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PartMaterial(Document):
	def validate(self):
		if self.color:
			meta = frappe.get_meta(self.color)
			if meta.istable or meta.issingle:
				frappe.throw(_("Color must reference a regular DocType, not a child table or Single DocType."))
