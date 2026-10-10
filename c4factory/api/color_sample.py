import json
import math

import frappe
from frappe import _
from frappe.utils import flt, today

from c4factory.api.sales_order_colors import get_part_list_colors, validate_colors


def submitted_quantities(sales_order, exclude=None, lock=False):
	# A locking read sees the latest committed submissions even when validation
	# previously opened a REPEATABLE READ snapshot in this transaction.
	rows = frappe.db.sql(
			"""select i.sales_order_item, i.qty
			from `tabColor Sample Item` i
			inner join `tabColor sample` s on s.name = i.parent
			where s.sales_order = %(sales_order)s and s.docstatus = 1
			and i.parenttype = 'Color sample' and i.parentfield = 'items'
			and s.name != %(exclude)s
			""" + (" for update" if lock else ""),
			{"sales_order": sales_order, "exclude": exclude or ""}, as_dict=True,
		)
	quantities = {}
	for row in rows:
		quantities[row.sales_order_item] = quantities.get(row.sales_order_item, 0) + flt(row.qty)
	return quantities


def get_order(sales_order):
	order = frappe.get_doc("Sales Order", sales_order)
	order.check_permission("read")
	if order.docstatus != 1:
		frappe.throw(_("Color Samples can only be created against a submitted Sales Order."))
	return order


@frappe.whitelist()
def get_available_items(sales_order):
	order = get_order(sales_order)
	used = submitted_quantities(order.name)
	return [
		{
			"sales_order_item": row.name, "item_code": row.item_code,
			"item_name": row.item_name, "order_qty": row.qty,
			"submitted_qty": used.get(row.name, 0),
			"remaining_qty": max(0, flt(row.qty) - used.get(row.name, 0)),
			"part_list": row.get("custom_part_list") or row.get("part_list"),
			"uom": row.uom,
		}
		for row in order.items
	]


def source_colors(row):
	part_list = row.get("custom_part_list") or row.get("part_list")
	if not part_list:
		frappe.throw(_("Item {0} does not have a Part List.").format(row.item_code))
	config = get_part_list_colors(part_list)
	try:
		stored = json.loads(row.get("custom_color_sample_data") or "{}")
	except (ValueError, TypeError):
		stored = {}
	matching = isinstance(stored, dict) and stored.get("part_list") == part_list
	choices = {
		choice.get("source_row"): choice
		for choice in (stored.get("rows") or []) if isinstance(choice, dict)
	} if matching and isinstance(stored.get("rows"), list) else {}
	for material in config["rows"]:
		choice = choices.get(material["source_row"], {})
		if choice.get("color_doctype") == material["color_doctype"]:
			material["color"] = choice.get("color")
	wood = row.get("custom_wood") or config["wood_color"]
	metal = row.get("custom_metal") or config["metal_color"]
	return {
		"custom_part_list": part_list,
		"custom_wood_color_doctype": config["wood_color_doctype"],
		"custom_wood": wood, "custom_metal": metal,
		"custom_color_sample_data": json.dumps({
			"part_list": part_list, "headers_initialized": True, "rows": config["rows"],
		}),
	}


@frappe.whitelist()
def make_color_sample(sales_order, selections):
	order = get_order(sales_order)
	selections = frappe.parse_json(selections)
	if not isinstance(selections, list) or not selections:
		frappe.throw(_("Select at least one Sales Order item."))
	target = frappe.new_doc("Color sample")
	target.check_permission("create")
	target.sales_order = order.name
	target.project = order.get("project")
	target.date = today()
	by_name = {row.name: row for row in order.items}
	for selection in selections:
		if not isinstance(selection, dict) or selection.get("sales_order_item") not in by_name:
			frappe.throw(_("Select an item belonging to this Sales Order."))
		source = by_name[selection["sales_order_item"]]
		values = source_colors(source)
		values.update({
			"sales_order_item": source.name, "item_code": source.item_code,
			"item_name": source.item_name, "uom": source.uom,
			"qty": selection.get("qty"), "order_qty": source.qty,
		})
		target.append("items", values)
	validate_sample(target)
	return target


def validate_sample(doc, lock=False):
	if lock:
		# Serialize submissions against one order before calculating the balance.
		frappe.db.sql("select name from `tabSales Order` where name = %s for update", doc.sales_order)
	order = get_order(doc.sales_order)
	doc.project = order.get("project")
	if not doc.get("items"):
		frappe.throw(_("Select at least one Sales Order item."))
	by_name = {row.name: row for row in order.items}
	used = submitted_quantities(order.name, doc.name, lock=lock)
	requested = {}
	for item in doc.items:
		source = by_name.get(item.sales_order_item)
		if not source:
			frappe.throw(_("Row {0}: Item does not belong to this Sales Order.").format(item.idx))
		qty = flt(item.qty)
		if not math.isfinite(qty) or qty <= 0:
			frappe.throw(_("Row {0}: Quantity must be greater than zero.").format(item.idx))
		requested[source.name] = requested.get(source.name, 0) + qty
		balance = max(0, flt(source.qty) - used.get(source.name, 0))
		if requested[source.name] > balance + 1e-9:
			frappe.throw(_("Row {0}: Only {1} remains available for item {2}.").format(item.idx, balance, source.item_code))
		item.item_code = source.item_code
		item.item_name = source.item_name
		item.uom = source.uom
		item.qty = qty
		item.order_qty = source.qty
		item.remaining_qty = balance
		baseline = source_colors(source)
		if item.get("custom_part_list") != baseline["custom_part_list"] or not item.get("custom_color_sample_data"):
			item.update(baseline)
	validate_colors(doc)
	# Unchecked materials allow header changes, but no individual row override.
	for item in doc.items:
		source = by_name[item.sales_order_item]
		baseline = json.loads(source_colors(source)["custom_color_sample_data"])
		original = {row["source_row"]: row for row in baseline["rows"]}
		for row in json.loads(item.custom_color_sample_data)["rows"]:
			if row["edite_color"]:
				continue
			allowed = [original[row["source_row"]]["color"]]
			if row["source_table"] == "panel_materials":
				allowed.append(item.custom_wood)
			elif row["source_table"] == "metal_material":
				allowed.append(item.custom_metal)
			if row["color"] not in allowed:
				frappe.throw(_("Row {0}: Individual color editing is not enabled for material {1}.").format(item.idx, row["material"]))
