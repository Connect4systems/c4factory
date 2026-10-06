import frappe
from frappe.model.document import Document


PDS_ITEM_SPCS_FIELDS = (
	"wood", "top", "modesty", "drawer_body", "drawer_face", "plexi",
	"metal", "fabric", "glass", "direction", "additional_notes",
)


class PDSRequest(Document):
	def validate(self):
		for row in self.get("items") or []:
			if not row.part_list:
				continue
			part_list = frappe.db.get_value(
				"Part List", row.part_list, ["product", "disable", "docstatus"], as_dict=True
			)
			if not part_list or part_list.product != row.item or part_list.disable or part_list.docstatus == 2:
				frappe.throw(f"Row {row.idx}: select an enabled, non-cancelled Part List for this Item.")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_part_lists(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe._dict(filters or {})
	if not filters.item:
		return []
	return frappe.get_list(
		"Part List",
		filters={
			"product": filters.item,
			"disable": 0,
			"docstatus": ["<", 2],
			"name": ["like", f"%{txt}%"],
		},
		fields=["name", "product"],
		order_by="modified desc",
		start=start,
		page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
def create_part_list_for_item(item, qty=1, pds_request=None, pds_request_item=None):
	if not item:
		frappe.throw("Please set Item before creating a Part List.")
	if not pds_request or not pds_request_item:
		frappe.throw("Please save the PDS Request before creating a Part List.")
	request = frappe.get_doc("PDS Request", pds_request)
	request.check_permission("write")
	if request.docstatus != 0:
		frappe.throw("Part List links can only be changed on a draft PDS Request.")
	row = next((row for row in request.get("items") or [] if row.name == pds_request_item), None)
	if not row:
		frappe.throw("Invalid PDS Request row selected.")
	if row.item != item:
		frappe.throw("The selected Item does not match the saved PDS Request row.")
	item_doc = frappe.get_cached_doc("Item", item)
	part_list_values = {
		"doctype": "Part List",
		"product": item,
		"product_name": item_doc.item_name,
		"description": row.description,
		"product_image": row.image or item_doc.image,
		"width": item_doc.get("custom_width"),
		"hight": item_doc.get("custom_hight"),
		"depth": item_doc.get("custom_depth"),
		"wood_color": row.get("wood"),
		"metal_color": row.get("metal"),
	}
	for field in PDS_ITEM_SPCS_FIELDS:
		part_list_values[field] = row.get(field)
	part_list = frappe.get_doc(part_list_values)
	part_list.insert(ignore_permissions=False)
	frappe.db.set_value("PDS Request Item", row.name, "part_list", part_list.name, update_modified=False)
	return part_list.name
