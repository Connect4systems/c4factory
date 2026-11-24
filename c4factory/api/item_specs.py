"""Shared three-column specifications and exact Sales Order row mapping."""

SPEC_FIELDS = ("panel_specs", "metal_specs", "other_specs")
LEGACY_GROUPS = {
	"panel_specs": (("wood", "Wood"), ("top", "Top"), ("modesty", "Modesty"),
		("drawer_body", "Drawer Body"), ("drawer_face", "Drawer Face")),
	"metal_specs": (("metal", "Metal"),),
	"other_specs": (("plexi", "Plexi"), ("fabric", "Fabric"), ("leather", "Leather"),
		("glass", "Glass"), ("other", "Other")),
}


def spec_values(row, prefix=""):
	return {field: row.get(prefix + field) for field in SPEC_FIELDS}


def legacy_spec_values(row, prefix=""):
	"""Only migrate empty destinations; reruns never append the same values."""
	values = {}
	for field, sources in LEGACY_GROUPS.items():
		if row.get(prefix + field):
			continue
		lines = [f"{label}: {row.get(prefix + source)}" for source, label in sources
			if row.get(prefix + source)]
		if lines:
			values[prefix + field] = "\n".join(lines)
	return values


def part_list_source_values(request, row):
	"""Fetch from the originating order, never guess among repeated products."""
	import frappe
	from frappe import _

	order_name = request.get("sales_order")
	if not order_name:
		return spec_values(row)
	order = frappe.get_doc("Sales Order", order_name)
	order.check_permission("read")
	if row.get("sales_order_item"):
		matches = [item for item in order.items if item.name == row.sales_order_item and item.item_code == row.item]
	else:
		matches = [item for item in order.items if item.item_code == row.item]
	if len(matches) != 1:
		frappe.throw(_("Select the originating Sales Order Item on the PDS Request before creating a Part List; its source is missing or ambiguous."))
	return {**spec_values(matches[0], "custom_"), "sales_order": order.name,
		"sales_order_item": matches[0].name}
