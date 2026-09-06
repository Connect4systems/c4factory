import frappe
from frappe import _


def validate_material_color(doc, method=None):
	if not doc.meta.has_field("custom_material_color"):
		return
	target = frappe.db.get_value("Item Group", doc.item_group, "custom_color") if doc.item_group else None
	previous = doc.get_doc_before_save()
	if (
		(previous and previous.item_group != doc.item_group)
		or doc.get("custom_material_color_doctype") != target
		or not target
	):
		doc.custom_material_color = None
	doc.custom_material_color_doctype = target
	if target:
		meta = frappe.get_meta(target)
		if meta.istable or meta.issingle:
			frappe.throw(_("Item Group Color must reference a regular DocType, not a child table or Single DocType."))
	if doc.get("custom_material_color") and not frappe.db.exists(target, doc.custom_material_color):
		frappe.throw(_("Material Color must be an existing record in {0}.").format(target))
