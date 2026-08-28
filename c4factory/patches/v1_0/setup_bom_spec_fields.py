from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	custom_fields = {
		"BOM": [
			{
				"fieldname": "custom_spcs_tab",
				"label": "Spcs",
				"fieldtype": "Tab Break",
				"insert_after": "amended_from",
			},
			{
				"fieldname": "custom_item_image_preview",
				"label": "Item Image",
				"fieldtype": "Image",
				"options": "custom_item_image",
				"insert_after": "custom_spcs_tab",
			},
			{
				"fieldname": "custom_item_image",
				"label": "Item Image URL",
				"fieldtype": "Attach",
				"insert_after": "custom_item_image_preview",
			},
			{
				"fieldname": "custom_spcs_section",
				"label": "Specifications",
				"fieldtype": "Section Break",
				"insert_after": "custom_item_image",
			},
			{
				"fieldname": "custom_location_code",
				"label": "Location Code",
				"fieldtype": "Data",
				"insert_after": "custom_spcs_section",
			},
			{
				"fieldname": "custom_sub_code",
				"label": "Sub Code",
				"fieldtype": "Data",
				"insert_after": "custom_location_code",
			},
			{
				"fieldname": "custom_plexi",
				"label": "Plexi",
				"fieldtype": "Link",
				"options": "Plexi",
				"insert_after": "custom_sub_code",
			},
			{
				"fieldname": "custom_top",
				"label": "Top",
				"fieldtype": "Link",
				"options": "P-Wood",
				"insert_after": "custom_plexi",
			},
			{
				"fieldname": "custom_modesty",
				"label": "Modesty",
				"fieldtype": "Link",
				"options": "P-Wood",
				"insert_after": "custom_top",
			},
			{
				"fieldname": "custom_spcs_column_2",
				"fieldtype": "Column Break",
				"insert_after": "custom_modesty",
			},
			{
				"fieldname": "custom_wood",
				"label": "Wood",
				"fieldtype": "Link",
				"options": "P-Wood",
				"insert_after": "custom_spcs_column_2",
			},
			{
				"fieldname": "custom_metal",
				"label": "Metal",
				"fieldtype": "Link",
				"options": "P-Metal",
				"insert_after": "custom_wood",
			},
			{
				"fieldname": "custom_leather",
				"label": "Leather",
				"fieldtype": "Link",
				"options": "Leather",
				"insert_after": "custom_metal",
			},
			{
				"fieldname": "custom_drawer_body",
				"label": "Drawer Body",
				"fieldtype": "Link",
				"options": "P-Wood",
				"insert_after": "custom_leather",
			},
			{
				"fieldname": "custom_drawer_face",
				"label": "Drawer Face",
				"fieldtype": "Link",
				"options": "P-Wood",
				"insert_after": "custom_drawer_body",
			},
			{
				"fieldname": "custom_spcs_column_3",
				"fieldtype": "Column Break",
				"insert_after": "custom_drawer_face",
			},
			{
				"fieldname": "custom_glass",
				"label": "Glass",
				"fieldtype": "Link",
				"options": "P-Glass",
				"insert_after": "custom_spcs_column_3",
			},
			{
				"fieldname": "custom_fabric",
				"label": "Fabric",
				"fieldtype": "Link",
				"options": "P-Fabric",
				"insert_after": "custom_glass",
			},
			{
				"fieldname": "custom_direction",
				"label": "Direction",
				"fieldtype": "Select",
				"options": "Right\nLeft",
				"insert_after": "custom_fabric",
			},
			{
				"fieldname": "custom_spcs_column_4",
				"fieldtype": "Column Break",
				"insert_after": "custom_direction",
			},
			{
				"fieldname": "custom_other",
				"label": "Other",
				"fieldtype": "Small Text",
				"insert_after": "custom_spcs_column_4",
			},
			{
				"fieldname": "custom_spcs_column_5",
				"fieldtype": "Column Break",
				"insert_after": "custom_other",
			},
			{
				"fieldname": "custom_additional_notes",
				"label": "Additional Notes",
				"fieldtype": "Text",
				"insert_after": "custom_spcs_column_5",
			},
		]
	}

	create_custom_fields(custom_fields, update=True)
