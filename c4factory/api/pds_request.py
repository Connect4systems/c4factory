import frappe
from frappe import _
from frappe.utils import now_datetime, today

SALES_ORDER_ITEM_SPEC_FIELD_MAP = {
    "custom_location_code": "location_code",
    "custom_sub_code": "sub_code",
    "custom_panel_specs": "panel_specs",
    "custom_metal_specs": "metal_specs",
    "custom_other_specs": "other_specs",
    "custom_direction": "direction",
    "additional_notes": "additional_notes",
}


def get_pds_item_blockers(item_codes, exclude_request=None):
	"""Check globally, including records the current user cannot list."""
	item_codes = sorted(set(item_codes))
	if not item_codes:
		return {}
	blocked = {}
	for part in frappe.get_all("Part List", filters={
		"product": ["in", item_codes], "disable": 0, "docstatus": ["<", 2],
	}, fields=["product", "name"], order_by="name asc"):
		blocked.setdefault(part.product, _("an existing Part List ({0})").format(part.name))
	requests = frappe.db.sql("""
		select ri.item, r.name
		from `tabPDS Request Item` ri
		inner join `tabPDS Request` r on r.name = ri.parent
		where ri.parenttype = 'PDS Request' and r.docstatus < 2
		and ri.item in %(items)s and r.name != %(exclude)s
		order by r.name
	""", {"items": item_codes, "exclude": exclude_request or ""}, as_dict=True)
	for request in requests:
		blocked.setdefault(request.item, _("a previous PDS Request ({0})").format(request.name))
	return blocked


def validate_new_pds_items(doc):
	"""Recheck on save; existing rows remain editable as their design progresses."""
	previous = doc.get_doc_before_save()
	old_items = {row.name: row.item for row in previous.get("items") or []} if previous else {}
	new_rows = [row for row in doc.get("items") or []
		if row.item and old_items.get(row.name) != row.item]
	# Serialize concurrent requests for the same products until transaction commit.
	for item in sorted({row.item for row in new_rows}):
		frappe.db.sql("select name from `tabItem` where name = %s for update", (item,))
	blocked = get_pds_item_blockers([row.item for row in new_rows], exclude_request=doc.name)
	seen = set()
	for row in doc.get("items") or []:
		if not row.item:
			frappe.throw(_("Row {0}: Select an Item.").format(row.idx))
		if row.item in seen:
			frappe.throw(_("Row {0}: Item {1} is already included in this PDS Request.").format(row.idx, row.item))
		seen.add(row.item)
	for row in new_rows:
		if row.item in blocked:
			frappe.throw(_("Row {0}: Item {1} already has {2}. A duplicate PDS request is not allowed.")
				.format(row.idx, row.item, blocked[row.item]))


@frappe.whitelist()
def make_pds_request(sales_order: str):
	source = frappe.get_doc("Sales Order", sales_order)
	source.check_permission("read")
	return build_pds_request(source)


def build_pds_request(source, automatic=False):
	"""Share eligibility and mapping between manual and submission requests."""
	from c4factory.api.boq_items import boq_item_filters

	target = frappe.new_doc("PDS Request")
	if not automatic:
		target.check_permission("create")
	target.sales_order = source.name
	target.customer = source.customer
	target.technical_team = source.get("custom_technical_team")
	target.date = today()
	item_codes = list({row.item_code for row in source.items if row.item_code})
	filters = boq_item_filters()
	filters["name"] = ["in", item_codes]
	boq_items = set(frappe.get_all("Item", filters=filters, pluck="name")) if item_codes else set()
	blocked = get_pds_item_blockers([row.item_code for row in source.items if row.item_code])
	seen = set()
	item_cache = {}
	for row in sorted(source.items, key=lambda row: row.idx or 0):
		if (row.item_code not in boq_items or row.get("part_list") or row.get("custom_part_list")
			or row.item_code in blocked or row.item_code in seen):
			continue
		seen.add(row.item_code)
		if row.item_code not in item_cache:
			item_cache[row.item_code] = frappe.db.get_value(
				"Item", row.item_code, ["item_name", "image"], as_dict=True
			) or {}
		details = item_cache[row.item_code]
		values = {
			"sales_order_item": row.name,
			"item": row.item_code,
			"item_name": details.get("item_name"),
			"image": details.get("image"),
			"description": row.description,
			"qty": row.qty,
		}
		for source_field, target_field in SALES_ORDER_ITEM_SPEC_FIELD_MAP.items():
			values[target_field] = row.get(source_field)
		target.append("items", values)
	if not target.get("items"):
		if automatic:
			return None
		frappe.throw(_("No items need a PDS Request. Items must have an Item Type with BOQ Required enabled and no existing Part List or previous PDS Request."))
	return target


def on_sales_order_submit(doc, method=None):
	"""Persist a draft request in the Sales Order submission transaction."""
	if doc.docstatus != 1:
		return
	# Use the same ordered item locks as request validation before checking eligibility.
	for item in sorted({row.item_code for row in doc.items if row.item_code}):
		frappe.db.sql("select name from `tabItem` where name = %s for update", (item,))
	if frappe.db.exists("PDS Request", {"sales_order": doc.name, "docstatus": ["<", 2]}):
		return
	request = build_pds_request(doc, automatic=True)
	if request is not None:
		request.docstatus = 0
		# Like automatic Project creation, this is part of authorized order submission.
		request.insert(ignore_permissions=True)


def update_sales_order_part_list(part_list):
	"""Update only the originating row, including on submitted Sales Orders."""
	meta = frappe.get_meta("Sales Order Item")
	link_fields = [field.fieldname for field in meta.fields
		if field.fieldtype == "Link" and field.options == "Part List"]
	if not link_fields:
		return
	for request_row in frappe.get_all(
		"PDS Request Item", filters={"part_list": part_list.name, "parenttype": "PDS Request"},
		fields=["parent", "item", "sales_order_item"],
	):
		if request_row.item != part_list.product:
			continue
		request = frappe.db.get_value("PDS Request", request_row.parent, ["sales_order", "docstatus"], as_dict=True)
		if not request or not request.sales_order or request.docstatus == 2:
			continue
		status = frappe.db.get_value("Sales Order", request.sales_order, "docstatus")
		if status is None or status == 2:
			continue
		filters = {"parent": request.sales_order, "parenttype": "Sales Order", "item_code": part_list.product}
		if request_row.sales_order_item:
			filters["name"] = request_row.sales_order_item
		rows = frappe.get_all("Sales Order Item", filters=filters, fields=["name"])
		# Older requests lack row references: use the item only when unambiguous.
		if len(rows) != 1:
			continue
		if status == 1:
			from c4factory.api.sales_order_part_list import check_part_list_change
			current = frappe.db.get_value("Sales Order Item", rows[0].name, link_fields, as_dict=True)
			if any(current.get(field) != part_list.name for field in link_fields):
				check_part_list_change(request.sales_order, rows[0].name)
		frappe.db.set_value("Sales Order Item", rows[0].name, {field: part_list.name for field in link_fields})
		frappe.db.set_value("Sales Order", request.sales_order, "modified", now_datetime())
