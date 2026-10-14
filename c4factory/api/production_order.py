"""Production orders from approved samples, with quantities reserved on submission."""

import json
import math

import frappe
from frappe import _
from frappe.utils import flt, today

from c4factory.api.part_list_versions import copy_values

SNAPSHOT_FIELDS = (
	"product", "product_name", "description", "product_image", "width", "hight", "depth",
	"material_line", "metal_material_line", "pds_table", "panel_materials",
	"metal_material", "other_material", "accessorise_table",
)
TABLE_FIELDS = ("pds_table", "panel_materials", "metal_material", "other_material", "accessorise_table")


def get_sample(name):
	sample = frappe.get_doc("Color sample", name)
	sample.check_permission("read")
	if sample.docstatus != 1:
		frappe.throw(_("Production Orders require a submitted Color Sample."))
	return sample


def used_quantities(sample, exclude=None, lock=False):
	rows = frappe.db.sql("""
		select color_sample_item, qty from `tabProduction Order`
		where color_sample = %(sample)s and docstatus = 1 and name != %(exclude)s
	""" + (" for update" if lock else ""),
		{"sample": sample, "exclude": exclude or ""}, as_dict=True)
	used = {}
	for row in rows:
		used[row.color_sample_item] = used.get(row.color_sample_item, 0) + flt(row.qty)
	return used


@frappe.whitelist()
def get_available_items(color_sample):
	sample = get_sample(color_sample)
	used = used_quantities(sample.name)
	return [{"color_sample_item": row.name, "item_code": row.item_code,
		"item_name": row.item_name, "part_list": row.custom_part_list, "uom": row.uom,
		"sample_qty": row.qty, "ordered_qty": used.get(row.name, 0),
		"remaining_qty": max(0, flt(row.qty) - used.get(row.name, 0))}
		for row in sample.get("items") or []]


def snapshot_values(row):
	part = frappe.get_doc("Part List", row.custom_part_list)
	part.check_permission("read")
	if part.product != row.item_code or part.docstatus == 2:
		frappe.throw(_("The sample's Part List must belong to its product and must not be cancelled."))
	try:
		colors = json.loads(row.get("custom_color_sample_data") or "{}")
		if not isinstance(colors, dict) or colors.get("part_list") != part.name or not isinstance(colors.get("rows"), list):
			raise ValueError
	except (ValueError, TypeError):
		frappe.throw(_("The Color Sample has invalid color data."))
	choices = {choice.get("source_row"): choice for choice in colors["rows"] if isinstance(choice, dict)}
	values = copy_values(part)
	for field in ("panel_materials", "metal_material", "other_material"):
		for source, copied in zip(part.get(field) or [], values.get(field) or []):
			choice = choices.get(source.name)
			if choice:
				if choice.get("color_doctype") != source.color_doctype:
					frappe.throw(_("The Part List colors have changed since the sample was approved. Review the sample first."))
				copied["basic_color"] = choice.get("color")
	return {field: values.get(field) for field in SNAPSHOT_FIELDS}


def prepare_order(doc):
	"""Build a trusted snapshot on insertion; keep that snapshot on later edits."""
	previous = doc.get_doc_before_save()
	if previous:
		for field in ("color_sample", "color_sample_item", "part_list", "sales_order", "project", "uom", *SNAPSHOT_FIELDS):
			if field in TABLE_FIELDS:
				old = [copy_values(row) for row in previous.get(field) or []]
				current = [copy_values(row) for row in doc.get(field) or []]
			else:
				old, current = previous.get(field), doc.get(field)
			if old != current:
				frappe.throw(_("{0} is copied from the Color Sample and cannot be changed. Create a new Production Order instead.")
					.format(doc.meta.get_label(field)))
		return
	sample = get_sample(doc.color_sample)
	row = next((row for row in sample.get("items") or [] if row.name == doc.color_sample_item), None)
	if not row:
		frappe.throw(_("Select an item belonging to the Color Sample."))
	doc.sales_order = sample.sales_order
	doc.project = sample.project
	doc.part_list = row.custom_part_list
	doc.uom = row.uom
	for field, value in snapshot_values(row).items():
		doc.set(field, value)


def validate_order(doc, lock=False):
	if lock:
		# All submissions for a sample share this lock. A locking read of orders
		# below sees the latest committed reservations under REPEATABLE READ.
		current = frappe.db.sql("select docstatus from `tabColor sample` where name = %s for update",
			(doc.color_sample,), as_dict=True)
		if not current or current[0].docstatus != 1:
			frappe.throw(_("Production Orders require a submitted Color Sample."))
	sample = get_sample(doc.color_sample)
	row = next((row for row in sample.get("items") or [] if row.name == doc.color_sample_item), None)
	if not row or row.item_code != doc.product:
		frappe.throw(_("The product must match the selected Color Sample item."))
	qty = flt(doc.qty)
	if not math.isfinite(qty) or qty <= 0:
		frappe.throw(_("Production Quantity must be a positive number."))
	used = used_quantities(sample.name, exclude=doc.name, lock=lock).get(row.name, 0)
	balance = max(0, flt(row.qty) - used)
	if qty > balance + 1e-9:
		frappe.throw(_("Only {0} remains available for product {1} in this Color Sample.").format(balance, row.item_code))
	doc.qty = qty
	doc.sample_qty = row.qty
	doc.ordered_qty = used
	doc.remaining_qty = max(0, balance - qty)


@frappe.whitelist()
def make_production_order(color_sample, color_sample_item, qty):
	doc = frappe.new_doc("Production Order")
	doc.check_permission("create")
	doc.color_sample = color_sample
	doc.color_sample_item = color_sample_item
	doc.qty = qty
	doc.date = today()
	prepare_order(doc)
	validate_order(doc)
	return doc


def prevent_sample_cancel(doc, method=None):
	frappe.db.sql("select name from `tabColor sample` where name = %s for update", (doc.name,))
	orders = frappe.db.sql("""select name from `tabProduction Order`
		where color_sample = %s and docstatus = 1 limit 1 for update""", (doc.name,))
	if orders:
		frappe.throw(_("Cancel the submitted Production Orders before cancelling this Color Sample."))
