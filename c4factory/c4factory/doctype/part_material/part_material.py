import frappe
from frappe.model.document import Document
from c4factory.api.part_list_material_colors import validate_palette_color


class PartMaterial(Document):
	def validate(self):
		validate_palette_color(self.get("color_palette"), self.get("color"))
