# Copyright (c) 2026, Connect 4 Systems and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PartList(Document):
	def on_submit(self):
		from c4factory.api.pds_request import update_sales_order_part_list

		update_sales_order_part_list(self)
