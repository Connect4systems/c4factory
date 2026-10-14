"""Part List snapshots, product activation, and the BOQ-style selector."""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

ITEM_LINES = {
	"Standard Lines": ("Standard Lines", True),
	"Customized Product": ("Customized Product", False),
	"Upholstery": ("Upholstery", True),
	"PU": ("PU", True),
	"Outsource": ("Outsource", True),
	"Home": ("HOME", True),
	"Archi Touch Chairs": ("Archi Chairs", True),
}
LAYOUT_TYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Image", "Button", "Heading"}
COPY_EXCLUSIONS = {"amended_from", "version_of"}


def copy_values(doc):
	"""Copy business data, including attachment URLs, without document identities."""
	values = {}
	for field in doc.meta.fields:
		if field.fieldname in COPY_EXCLUSIONS or field.fieldtype in LAYOUT_TYPES:
			continue
		if field.fieldtype in ("Table", "Table MultiSelect"):
			values[field.fieldname] = [copy_values(row) for row in doc.get(field.fieldname) or []]
		else:
			values[field.fieldname] = doc.get(field.fieldname)
	return values


@frappe.whitelist()
def get_copy_payload(source, target=None, new_version=False):
	part = frappe.get_doc("Part List", source)
	part.check_permission("read")
	if part.docstatus == 2 or part.disable:
		frappe.throw(_("Select an enabled, non-cancelled Part List."))
	if target:
		current = frappe.get_doc("Part List", target)
		current.check_permission("write")
		if current.docstatus != 0 or target == source:
			frappe.throw(_("Import into a different draft Part List."))
	elif not frappe.has_permission("Part List", "create"):
		frappe.throw(_("You do not have permission to create Part Lists."), frappe.PermissionError)
	if cint(new_version) and part.docstatus != 1:
		frappe.throw(_("New Version requires a submitted Part List."))
	return {"source": part.name, "values": copy_values(part)}


def allowed_item_groups(item_line):
	config = ITEM_LINES.get(item_line)
	if not config:
		return []
	group, descendants = config
	bounds = frappe.db.get_value("Item Group", group, ["lft", "rgt", "is_group"], as_dict=True)
	if not bounds:
		return []
	if not descendants:
		return [group] if not bounds.is_group else []
	return frappe.get_all("Item Group", filters={
		"lft": [">=", bounds.lft], "rgt": ["<=", bounds.rgt], "is_group": 0,
	}, pluck="name")


@frappe.whitelist()
def get_selector_items(item_line, material_line=None, item_group=None, brand=None, txt=None,
	width=None, height=None, depth=None, limit=20, page=1, target=None):
	if not frappe.has_permission("Part List", "read"):
		frappe.throw(_("You do not have permission to read Part Lists."), frappe.PermissionError)
	groups = allowed_item_groups(item_line)
	if not groups or (item_group and item_group not in groups):
		return {"items": [], "total": 0, "allowed_item_groups": groups}
	filters = {"docstatus": ["<", 2], "disable": 0}
	if target:
		filters["name"] = ["!=", target]
	# get_list applies Part List permissions; Item details are permission filtered too.
	parts = frappe.get_list("Part List", filters=filters,
		fields=["name", "product", "product_name", "description", "product_image", "material_line", "width", "hight", "depth"],
		limit_page_length=0, order_by="name asc")
	codes = list({part.product for part in parts if part.product})
	items = frappe.get_list("Item", filters={"name": ["in", codes], "disabled": 0},
		fields=["name", "item_name", "item_group", "brand", "stock_uom", "image"], limit_page_length=0) if codes else []
	by_code = {item.name: item for item in items}
	matches = []
	query = (txt or "").strip().casefold()
	for part in parts:
		item = by_code.get(part.product)
		if not item or item.item_group not in groups:
			continue
		if item_group and item.item_group != item_group:
			continue
		if material_line and part.material_line != material_line:
			continue
		if brand and item.brand != brand:
			continue
		if any(requested not in (None, "", 0, "0") and abs(flt(value) - flt(requested)) > 1e-6
			for value, requested in ((part.width, width), (part.hight, height), (part.depth, depth))):
			continue
		if query and not any(query in str(value or "").casefold()
			for value in (part.name, part.product, part.product_name, part.description)):
			continue
		matches.append({"part_list_id": part.name, "item_code": part.product,
			"item_name": part.product_name or item.item_name, "description": part.description,
			"image": part.product_image or item.image, "material_line": part.material_line,
			"item_group": item.item_group, "brand": item.brand, "uom": item.stock_uom,
			"width": part.width, "height": part.hight, "depth": part.depth})
	page_size = max(1, min(cint(limit) or 20, 100))
	start = (max(1, cint(page)) - 1) * page_size
	return {"items": matches[start:start + page_size], "total": len(matches), "allowed_item_groups": groups}


def activate_for_product(part):
	"""Activate and repoint live product references in the submission transaction."""
	if part.disable:
		frappe.throw(_("An active Part List cannot be disabled."))
	# The Item lock serializes two versions submitted concurrently for one product.
	frappe.db.sql("select name from `tabItem` where name = %s for update", part.product)
	for old in frappe.get_all("Part List", filters={"product": part.product,
		"name": ["!=", part.name], "is_default": 1}, pluck="name"):
		frappe.db.set_value("Part List", old, "is_default", 0)
	frappe.db.set_value("Part List", part.name, "is_default", 1, update_modified=False)
	part.is_default = 1
	from c4factory.api.sales_order_colors import get_part_list_colors
	payload = json.dumps({"part_list": part.name, "rows": get_part_list_colors(part.name)["rows"]})
	for parenttype, childtype, product_field in (
		("Sales Order", "Sales Order Item", "item_code"), ("PDS Request", "PDS Request Item", "item"),
	):
		meta = frappe.get_meta(childtype)
		link_fields = [field.fieldname for field in meta.fields
			if field.fieldtype == "Link" and field.options == "Part List"]
		if not link_fields:
			continue
		rows = frappe.get_all(childtype, filters={product_field: part.product, "parenttype": parenttype,
			"parentfield": "items"}, fields=["name", "parent", *link_fields], order_by="parent asc, idx asc")
		parents = sorted({row.parent for row in rows})
		for parent in parents:
			# Lock parents before checking status, updating links, and invalidating stale forms.
			frappe.db.sql(f"select name from `tab{parenttype}` where name = %s for update", parent)
			if frappe.db.get_value(parenttype, parent, "docstatus") not in (0, 1):
				continue
			changed = False
			for row in rows:
				if row.parent != parent or all(row.get(field) == part.name for field in link_fields):
					continue
				values = dict.fromkeys(link_fields, part.name)
				if parenttype == "Sales Order" and meta.has_field("custom_color_sample_data"):
					values["custom_color_sample_data"] = payload
				frappe.db.set_value(childtype, row.name, values, update_modified=False)
				changed = True
			if changed:
				frappe.db.set_value(parenttype, parent, "modified", now_datetime())


def link_copied_attachments(part):
	"""Give readers of a copied Part List access to its existing private PDS files."""
	urls = {row.get("arttach") for row in part.get("pds_table") or [] if row.get("arttach")}
	for url in urls:
		if frappe.db.exists("File", {"file_url": url, "attached_to_doctype": "Part List", "attached_to_name": part.name}):
			continue
		files = frappe.get_all("File", filters={"file_url": url}, fields=["name"], limit_page_length=1)
		if not files:
			continue
		file = frappe.get_doc("File", files[0].name)
		# Only reuse a file the submitting/saving user can already read.
		file.check_permission("read")
		frappe.get_doc({"doctype": "File", "file_name": file.file_name, "file_url": file.file_url,
			"is_private": file.is_private, "attached_to_doctype": "Part List", "attached_to_name": part.name,
			"attached_to_field": "pds_table"}).insert(ignore_permissions=True)


def set_sales_order_active_parts(doc, method=None):
	"""Resolve product defaults on the server too, including orders created by API."""
	if doc.docstatus != 0:
		return
	fields = [field.fieldname for field in frappe.get_meta("Sales Order Item").fields
		if field.fieldtype == "Link" and field.options == "Part List"]
	products = list({row.item_code for row in doc.items if row.item_code})
	if not fields or not products:
		return
	active = frappe.get_all("Part List", filters={"product": ["in", products], "docstatus": 1,
		"disable": 0, "is_default": 1}, fields=["name", "product"], order_by="modified desc")
	by_product = {}
	for part in active:
		by_product.setdefault(part.product, part.name)
	for row in doc.items:
		if row.item_code in by_product:
			for field in fields:
				row.set(field, by_product[row.item_code])
