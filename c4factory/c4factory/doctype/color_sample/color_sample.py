# Copyright (c) 2026, Connect 4 Systems and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from c4factory.api.color_sample import validate_sample


class Colorsample(Document):
	def validate(self):
		validate_sample(self)

	def before_submit(self):
		validate_sample(self, lock=True)
