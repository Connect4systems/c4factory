# Copyright (c) 2026, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ItemCodingRequest(Document):
	def before_submit(self):
		if not self.item_code:
			frappe.throw(_("Item Code is required before submitting an Item Coding Request."))
