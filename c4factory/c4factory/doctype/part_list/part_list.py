# Copyright (c) 2026, Connect 4 Systems and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PartList(Document):
	def before_validate(self):
		previous = self.get_doc_before_save()
		if not previous and self.get("material_line") is None and not self.get("version_of"):
			self.material_line = frappe.db.get_value("Item", self.product, "custom_material_line") if self.product else None
		if previous and self.get("metal_material_line") != previous.get("metal_material_line") and self.get("material_line") == previous.get("material_line"):
			self.material_line = self.metal_material_line
		self.metal_material_line = self.get("material_line")

	def before_submit(self):
		if self.get("version_of"):
			self.is_default = 1

	def on_update(self):
		from c4factory.api.part_list_versions import link_copied_attachments

		link_copied_attachments(self)

	def on_submit(self):
		from c4factory.api.part_list_versions import activate_for_product
		from c4factory.api.pds_request import update_sales_order_part_list

		if self.is_default:
			activate_for_product(self)
		else:
			update_sales_order_part_list(self)

	def on_update_after_submit(self):
		previous = self.get_doc_before_save()
		if self.is_default and previous and not previous.is_default:
			from c4factory.api.part_list_versions import activate_for_product

			activate_for_product(self)
