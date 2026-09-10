import frappe

from c4factory.patches.v1_0.setup_item_material_color import execute as setup_fields


def execute():
	# Remove only overrides of the properties owned by this feature.
	# Property Setters take precedence over the Custom Field definitions.
	for name in frappe.get_all(
		"Property Setter",
		filters={
			"doc_type": "Item",
			"field_name": ["in", ["custom_material_color_doctype", "custom_material_color"]],
			"property": ["in", [
				"label", "fieldtype", "options", "hidden", "read_only",
				"depends_on", "read_only_depends_on",
			]],
		},
		pluck="name",
	):
		frappe.delete_doc("Property Setter", name, ignore_permissions=True)
	setup_fields()
	frappe.clear_cache(doctype="Item")
