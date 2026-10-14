import frappe
from frappe.model.document import Document
from frappe.model.naming import getseries

from c4factory.api.production_order import prepare_order, validate_order


class ProductionOrder(Document):
	def autoname(self):
		prepare_order(self)
		prefix = f"PO-{self.product}-"
		self.name = prefix + getseries(prefix, 2)

	def before_validate(self):
		prepare_order(self)

	def validate(self):
		validate_order(self)

	def before_submit(self):
		validate_order(self, lock=True)

	def on_update(self):
		from c4factory.api.part_list_versions import link_copied_attachments

		link_copied_attachments(self)

	def before_cancel(self):
		# Serialize release with submissions using the same sample.
		frappe.db.sql("select name from `tabColor sample` where name = %s for update", (self.color_sample,))
