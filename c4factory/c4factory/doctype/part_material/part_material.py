import frappe
from frappe.model.document import Document
from c4factory.api.part_list_material_colors import validate_palette_color


class PartMaterial(Document):
	def validate(self):
		validate_palette_color(self.color_palette, self.color)
