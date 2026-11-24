"""Project progress is derived from transaction rows, never editable counters."""

import math

import frappe
from frappe import _
from frappe.utils import flt, today


def progress_status(qty, delivered, installed):
	return (
		"Not Delivered" if delivered <= 0 else "Fully Delivered" if delivered >= qty else "Partly Delivered",
		"Not Delivered" if delivered <= 0 else "Pending Installation" if installed <= 0
		else "Fully Installed" if installed >= delivered else "Partly Installed",
	)


def delivery_rows(sales_order):
	return frappe.db.sql("""
		select i.name, i.parent, i.so_detail, i.item_code, i.qty, i.stock_qty,
		 i.conversion_factor, i.installed_qty, i.description, d.is_return, d.return_against
		from `tabDelivery Note Item` i join `tabDelivery Note` d on d.name=i.parent
		where d.docstatus=1 and i.against_sales_order=%s
		order by d.posting_date, d.name, i.idx
	""", sales_order, as_dict=True)


def installed_quantities(names, exclude=None):
	if not names:
		return {}
	return dict(frappe.db.sql("""
		select i.prevdoc_detail_docname, sum(i.qty)
		from `tabInstallation Note Item` i join `tabInstallation Note` n on n.name=i.parent
		where n.docstatus=1 and i.prevdoc_detail_docname in %(names)s and n.name != %(exclude)s
		group by i.prevdoc_detail_docname
	""", {"names": names, "exclude": exclude or ""}))


def resolve_sales_order(project):
	"""Older Projects may only be linked from the Sales Order side."""
	if project.get("sales_order"):
		return project.sales_order
	if not project.get("name"):
		return None
	filters = {"project": project.name, "docstatus": 1}
	orders = frappe.get_all("Sales Order", filters=filters, pluck="name")
	if not orders and project.get("custom_project_no") and project.get("customer") and project.get("company"):
		orders = frappe.get_all("Sales Order", filters={
			"custom_project_no": str(project.custom_project_no), "customer": project.customer,
			"company": project.company, "docstatus": 1,
		}, pluck="name")
	if len(orders) == 1:
		project.sales_order = orders[0]
		return orders[0]
	if len(orders) > 1:
		frappe.throw(_("Multiple Sales Orders match this Project. Select its Sales Order before loading the BOQ."))
	return None


@frappe.whitelist()
def get_project_boq(project):
	doc = frappe.get_doc("Project", project)
	doc.check_permission("read")
	sales_order = resolve_sales_order(doc)
	if not sales_order:
		return {"rows": [], "sales_order": None, "active": False}
	order = frappe.get_doc("Sales Order", sales_order)
	order.check_permission("read")
	return {"rows": build_rows(doc), "sales_order": sales_order,
		"active": order.docstatus == 1 and order.status not in {"Closed", "On Hold", "Cancelled"}}


def build_rows(project):
	if not project.get("sales_order"):
		return []
	order = frappe.get_doc("Sales Order", project.sales_order)
	if not order.items:
		return []
	from c4factory.api.boq_items import boq_item_filters
	filters = boq_item_filters()
	filters["name"] = ["in", list({r.item_code for r in order.items})]
	required = set(frappe.get_all("Item", filters=filters, pluck="name"))
	deliveries = delivery_rows(order.name)
	installed = installed_quantities([d.name for d in deliveries if not d.is_return])
	requests = frappe.db.sql("""
		select i.item, i.sales_order_item, i.parent, r.sales_order
		from `tabPDS Request Item` i join `tabPDS Request` r on r.name=i.parent
		where r.docstatus<2 and i.item in %(items)s order by r.creation desc
	""", {"items": list({r.item_code for r in order.items})}, as_dict=True)
	existing = {r.get("sales_order_item"): r for r in project.get("custom_project_boq", [])}
	images = {r.name: r.image for r in frappe.get_all("Item",
		filters={"name": ["in", list({r.item_code for r in order.items})]}, fields=["name", "image"])}
	result = []
	for row in order.items:
		factor = flt(row.conversion_factor) or 1
		linked = [d for d in deliveries if d.so_detail == row.name]
		delivered = sum(flt(d.stock_qty) / factor for d in linked)
		installed_qty = sum(flt(installed.get(d.name)) * (flt(d.conversion_factor) or 1) / factor
			for d in linked if not d.is_return)
		part = row.get("custom_part_list") or row.get("part_list")
		valid_part = part and frappe.db.exists("Part List", {
			"name": part, "product": row.item_code, "docstatus": 1, "disable": 0})
		request = next((r.parent for r in requests if r.item == row.item_code
			and r.sales_order_item == row.name), None)
		request = request or next((r.parent for r in requests if r.item == row.item_code), None)
		pds_status = "No Part List Required" if row.item_code not in required else "PDS Required"
		if row.item_code in required:
			if valid_part:
				pds_status = f"PDS: {part}"
			elif request:
				pds_status = f"PDS Request: {request}"
		delivery_status, installation_status = progress_status(flt(row.qty), delivered, installed_qty)
		previous = existing.get(row.name)
		note = previous.get("note") if previous and (previous.get("note_initialized") or previous.get("note")) else row.get("custom_note")
		result.append({
			"sales_order_item": row.name, "item_code": row.item_code, "item_name": row.item_name,
			"description": row.description, "actual_qty": row.qty, "uom": row.uom,
			"note": note, "note_initialized": 1, "image": images.get(row.item_code),
			"delivered_qty": delivered, "installed_qty": installed_qty,
			"pds_status": pds_status, "pds_request": request,
			"part_list": part if valid_part else None,
			"delivery_status": delivery_status, "installation_status": installation_status,
		})
	return result


def onload(doc, method=None):
	if resolve_sales_order(doc):
		doc.set_onload("project_boq", build_rows(doc))
		order = frappe.db.get_value("Sales Order", doc.sales_order, ["docstatus", "status", "customer"], as_dict=True)
		doc.customer = order.customer
		doc.set_onload("project_boq_active", order.docstatus == 1 and order.status not in {"Closed", "On Hold", "Cancelled"})


def validate_project(doc, method=None):
	if resolve_sales_order(doc):
		doc.customer = frappe.db.get_value("Sales Order", doc.sales_order, "customer")
		doc.custom_project_title = frappe.db.get_value("Sales Order", doc.sales_order, "custom_project_title")
		doc.custom_sales_partner = frappe.db.get_value("Sales Order", doc.sales_order, "sales_partner")
		doc.set("custom_project_boq", build_rows(doc))


def sync_progress(doc, method=None):
	"""Persist derived rows for reports as well as the live Project display."""
	orders = set()
	if doc.doctype == "Sales Order":
		orders.add(doc.name)
	elif doc.doctype == "Delivery Note":
		orders.update(r.against_sales_order for r in doc.items if r.against_sales_order)
	elif doc.doctype == "Installation Note":
		refs = [r.prevdoc_detail_docname for r in doc.items if r.prevdoc_detail_docname]
		if refs:
			orders.update(frappe.get_all("Delivery Note Item", filters={"name": ["in", refs]}, pluck="against_sales_order"))
	elif doc.doctype in {"PDS Request", "Part List"}:
		items = [r.item for r in doc.items] if doc.doctype == "PDS Request" else [doc.product]
		if items:
			orders.update(frappe.get_all("Sales Order Item", filters={"item_code": ["in", items]}, pluck="parent"))
	orders.discard(None)
	orders.discard("")
	if not orders:
		return
	for name in frappe.get_all("Project", filters={"sales_order": ["in", sorted(orders)]}, pluck="name", order_by="name"):
		frappe.db.sql("select name from `tabProject` where name=%s for update", name)
		project = frappe.get_doc("Project", name)
		project.set("custom_project_boq", build_rows(project))
		# Only derived counters change; do not run unrelated Project workflows or alter its modified timestamp.
		frappe.db.delete("Project BOQ Item", {"parent": name, "parenttype": "Project", "parentfield": "custom_project_boq"})
		for row in project.custom_project_boq:
			row.db_insert()


def active_order(project):
	doc = frappe.get_doc("Project", project)
	doc.check_permission("read")
	if not resolve_sales_order(doc):
		frappe.throw(_("This Project has no Sales Order."))
	order = frappe.get_doc("Sales Order", doc.sales_order)
	order.check_permission("read")
	frappe.db.sql("select name from `tabSales Order` where name=%s for update", order.name)
	if order.docstatus != 1 or order.status in {"Closed", "On Hold", "Cancelled"}:
		frappe.throw(_("Delivery and installation require an active submitted Sales Order."))
	return doc, order


def selections(rows):
	rows = frappe.parse_json(rows) if isinstance(rows, str) else rows
	if not isinstance(rows, list) or not rows:
		frappe.throw(_("Select at least one row."))
	result = {}
	for row in rows:
		key, qty = row.get("sales_order_item"), flt(row.get("qty"))
		if not key or key in result or not math.isfinite(qty) or qty <= 0:
			frappe.throw(_("Select unique rows with a positive quantity."))
		result[key] = qty
	return result


def draft_conflicts(doctype, order, selected):
	if doctype == "Delivery Note":
		names = frappe.db.sql("""select distinct i.parent from `tabDelivery Note Item` i
			join `tabDelivery Note` d on d.name=i.parent where d.docstatus=0
			and i.against_sales_order=%s and i.so_detail in %s""", (order, tuple(selected)))
	else:
		names = frappe.db.sql("""select distinct i.parent from `tabInstallation Note Item` i
			join `tabInstallation Note` n on n.name=i.parent
			join `tabDelivery Note Item` d on d.name=i.prevdoc_detail_docname
			where n.docstatus=0 and d.against_sales_order=%s and d.so_detail in %s""",
			(order, tuple(selected)))
	# Only reveal draft names the user can read.
	if names:
		visible = [name for (name,) in names if frappe.has_permission(doctype, "read", doc=name)]
		frappe.throw(_("Existing draft {0}: {1}. Review it before creating another draft.").format(
			doctype, ", ".join(visible) or _("contact the document owner")))


@frappe.whitelist()
def create_delivery_note(project, rows):
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
	from erpnext.stock.doctype.packed_item.packed_item import make_packing_list
	doc, order = active_order(project)
	selected = selections(rows)
	progress = {r["sales_order_item"]: r for r in build_rows(doc)}
	for key, qty in selected.items():
		if key not in progress or qty > flt(progress[key]["actual_qty"]) - progress[key]["delivered_qty"] + 1e-9:
			frappe.throw(_("Selected quantity exceeds the remaining order quantity."))
	draft_conflicts("Delivery Note", order.name, selected)
	target = make_delivery_note(order.name)
	target.check_permission("create")
	target.set("items", [r for r in target.items if r.so_detail in selected])
	if {r.so_detail for r in target.items} != set(selected):
		frappe.throw(_("Some selected rows are not eligible for a Delivery Note."))
	for row in target.items:
		row.qty = selected[row.so_detail]
		row.project = doc.name
	target.project = doc.name
	target.run_method("set_missing_values")
	target.run_method("calculate_taxes_and_totals")
	make_packing_list(target)
	target.insert()
	return target.name


@frappe.whitelist()
def installation_options(project, sales_order_item):
	_, order = active_order(project)
	if not any(r.name == sales_order_item for r in order.items):
		frappe.throw(_("Invalid Sales Order row."))
	rows = [r for r in delivery_rows(order.name) if r.so_detail == sales_order_item and not r.is_return]
	installed = installed_quantities([r.name for r in rows])
	options = []
	for row in rows:
		returned = returned_qty(row)
		remaining = flt(row.qty) - returned - flt(installed.get(row.name))
		if remaining > 0 and frappe.has_permission("Delivery Note", "read", doc=row.parent):
			options.append({"delivery_note": row.parent, "delivery_note_item": row.name,
				"qty": remaining, "item_code": row.item_code})
	return options


def returned_qty(row):
	# dn_detail identifies the precise original row, including split deliveries.
	return flt(frappe.db.sql("""select -coalesce(sum(i.stock_qty),0)
		from `tabDelivery Note Item` i join `tabDelivery Note` d on d.name=i.parent
		where d.docstatus=1 and d.is_return=1 and d.return_against=%s
		and (i.dn_detail=%s or (coalesce(i.dn_detail,'')='' and i.so_detail=%s))
	""", (row.parent, row.name, row.so_detail))[0][0]) / (flt(row.conversion_factor) or 1)


@frappe.whitelist()
def create_installation_note(project, sales_order_item, rows):
	doc, order = active_order(project)
	available = {r["delivery_note_item"]: r for r in installation_options(project, sales_order_item)}
	selected = selections(rows)  # Keys are delivery item IDs for this action.
	draft_conflicts("Installation Note", order.name, [sales_order_item])
	target = frappe.new_doc("Installation Note")
	target.check_permission("create")
	target.update({"customer": order.customer, "company": order.company,
		"customer_name": order.customer_name, "territory": order.territory,
		"customer_group": order.customer_group, "inst_date": today(), "custom_project": doc.name})
	for key, qty in selected.items():
		if key not in available or qty > available[key]["qty"] + 1e-9:
			frappe.throw(_("Installation quantity exceeds the delivered quantity available."))
		delivery = frappe.get_doc("Delivery Note", available[key]["delivery_note"])
		delivery.check_permission("read")
		row = next(r for r in delivery.items if r.name == key)
		target.append("items", {"item_code": row.item_code, "description": row.description, "qty": qty,
			"prevdoc_doctype": "Delivery Note", "prevdoc_docname": delivery.name,
			"prevdoc_detail_docname": key})
	target.insert()
	return target.name


def validate_installation(doc, method=None):
	refs = sorted({r.prevdoc_detail_docname for r in doc.items if r.prevdoc_detail_docname})
	if not refs:
		return
	frappe.db.sql("select name from `tabDelivery Note Item` where name in %s order by name for update", (refs,))
	installed = installed_quantities(refs, exclude=doc.name)
	requested = {}
	projects = set()
	for row in doc.items:
		if not row.prevdoc_detail_docname:
			continue
		source = frappe.get_doc("Delivery Note Item", row.prevdoc_detail_docname)
		parent = frappe.get_doc("Delivery Note", source.parent)
		if (parent.docstatus != 1 or parent.is_return or parent.customer != doc.customer
			or parent.company != doc.company or source.item_code != row.item_code
			or row.prevdoc_docname != parent.name):
			frappe.throw(_("Installation must reference a matching submitted delivery row."))
		if source.get("against_sales_order"):
			status = frappe.db.get_value("Sales Order", source.against_sales_order, ["docstatus", "status"], as_dict=True)
			if status.docstatus != 1 or status.status in {"Closed", "On Hold", "Cancelled"}:
				frappe.throw(_("Installation requires an active submitted Sales Order."))
		if source.get("project"):
			projects.add(source.project)
		qty = flt(row.qty)
		requested[source.name] = requested.get(source.name, 0) + qty
		if not math.isfinite(qty) or qty <= 0 or requested[source.name] + flt(installed.get(source.name)) > flt(source.qty) - returned_qty(source) + 1e-9:
			frappe.throw(_("Installed quantity cannot exceed net delivered quantity."))
	if doc.get("custom_project") and projects != {doc.custom_project}:
		frappe.throw(_("Installation delivery rows must belong to the selected Project."))
	if len(projects) == 1:
		doc.custom_project = next(iter(projects))


def guard_delivery_change(doc, method=None):
	"""Keep already installed units backed by submitted deliveries."""
	if method == "before_submit" and not doc.get("is_return"):
		return
	if method == "before_cancel" and doc.get("is_return"):
		return
	orders = sorted({r.against_sales_order for r in doc.items if r.against_sales_order})
	for order in orders:
		frappe.db.sql("select name from `tabSales Order` where name=%s for update", order)
	refs = [r.name for r in doc.items]
	if doc.get("is_return"):
		refs = []
		for row in doc.items:
			if row.get("dn_detail"):
				refs.append(row.dn_detail)
			else:
				refs.extend(frappe.get_all("Delivery Note Item",
					filters={"parent": doc.return_against, "so_detail": row.so_detail}, pluck="name"))
	if refs:
		frappe.db.sql("select name from `tabDelivery Note Item` where name in %s order by name for update", (sorted(refs),))
	installed = installed_quantities(refs)
	if any(flt(qty) > 0 for qty in installed.values()):
		frappe.throw(_("Cancel the linked Installation Notes before returning or cancelling this delivery."))
