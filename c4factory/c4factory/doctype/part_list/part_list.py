# Copyright (c) 2026, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PartList(Document):
	def before_validate(self):
		item = frappe.db.get_value(
			"Item", self.product, ["custom_material_line", "image"], as_dict=True
		) if self.product else None
		self.material_line = item.get("custom_material_line") if item else None
		self.metal_material_line = self.material_line
		self.product_image = item.get("image") if item else None

	def on_submit(self):
		from c4factory.api.pds_request import update_sales_order_part_list

		update_sales_order_part_list(self)
