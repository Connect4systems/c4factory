"""Install Spcs sections in child rows and a Spcs tab in Part List."""

import json
from collections import defaultdict

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from c4factory.api.item_specs import LEGACY_GROUPS, SPEC_FIELDS, legacy_spec_values, spec_values

LEGACY_FIELDS = tuple(source for group in LEGACY_GROUPS.values() for source, label in group)
SO_LEGACY_LAYOUT = (
	"custom_section_break_dfrqw", "custom_column_break_dw4h6", "custom_column_break_ldrqw",
	"custom_column_break_yv9mn", "custom_column_break_1byqx",
)
PDS_LEGACY_LAYOUT = ("section_break_razl", "column_break_nale", "column_break_yvsv")


def spec_layout(prefix="", read_only=0, tabbed=False):
	return ([{"fieldname": prefix + "spcs_tab", "fieldtype": "Tab Break", "label": "Spcs"}]
		if tabbed else []) + [
		{"fieldname": prefix + "spcs_section", "fieldtype": "Section Break", "label": "" if tabbed else "Spcs"},
		{"fieldname": prefix + "panel_specs", "fieldtype": "Data", "label": "Panel", "read_only": read_only},
		{"fieldname": prefix + "spcs_metal_column", "fieldtype": "Column Break"},
		{"fieldname": prefix + "metal_specs", "fieldtype": "Data", "label": "Metal", "read_only": read_only},
		{"fieldname": prefix + "spcs_other_column", "fieldtype": "Column Break"},
		{"fieldname": prefix + "other_specs", "fieldtype": "Data", "label": "Other", "read_only": read_only},
	]


def setup_fields():
	# A hidden Tab Break still enables Frappe's tabbed layout. Remove the obsolete
	# layout field entirely; the three specification data fields are retained.
	for doctype, tab in (("Sales Order Item", "custom_spcs_tab"),
		("PDS Request Item", "spcs_tab"), ("Project BOQ Item", "spcs_tab")):
		for setter in frappe.get_all("Property Setter", filters={"doc_type": doctype, "field_name": tab}, pluck="name"):
			frappe.delete_doc("Property Setter", setter, ignore_permissions=True)
	if frappe.db.exists("Custom Field", "Sales Order Item-custom_spcs_tab"):
		frappe.delete_doc("Custom Field", "Sales Order Item-custom_spcs_tab", ignore_permissions=True)
	frappe.clear_cache(doctype="Sales Order Item")
	meta = frappe.get_meta("Sales Order Item", cached=False)
	block = spec_layout("custom_")
	new_names = {field["fieldname"] for field in block}
	anchor = next(field.fieldname for field in reversed(meta.fields) if field.fieldname not in new_names)
	for field in block:
		field["insert_after"] = anchor
		anchor = field["fieldname"]
	create_custom_fields({"Sales Order Item": block}, update=True)
	for doctype, prefix, legacy_layout in (
		("Sales Order Item", "custom_", SO_LEGACY_LAYOUT),
		("PDS Request Item", "", PDS_LEGACY_LAYOUT),
		("Part List", "", ()),
		("Project BOQ Item", "", ()),
	):
		meta = frappe.get_meta(doctype, cached=False)
		names = {field.fieldname for field in meta.fields}
		# Reapply the type after customization sync, including existing sites.
		for field in SPEC_FIELDS:
			make_property_setter(doctype, prefix + field, "fieldtype", "Data", "Data")
		for name in [prefix + field for field in LEGACY_FIELDS] + list(legacy_layout):
			if name in names and doctype in {"Sales Order Item", "PDS Request Item"}:
				make_property_setter(doctype, name, "hidden", 1, "Check")
				make_property_setter(doctype, name, "reqd", 0, "Check")
				make_property_setter(doctype, name, "print_hide", 1, "Check")
		layout = [field["fieldname"] for field in spec_layout(prefix, tabbed=doctype == "Part List")]
		# Retain site-specific fields and put only the new three-column block in Spcs.
		obsolete = {prefix + "spcs_tab"} if doctype != "Part List" else set()
		order = [field.fieldname for field in meta.fields if field.fieldname not in layout and field.fieldname not in obsolete]
		if doctype == "PDS Request Item":
			notes = [name for name in ("spec_notes_section", "direction", "additional_notes") if name in names]
			order = [name for name in order if name not in notes] + notes
		order += layout
		make_property_setter(doctype, None, "field_order", json.dumps(order), "Data", for_doctype=True)
		frappe.clear_cache(doctype=doctype)


def migrate_legacy(doctype, prefix):
	# Removed Custom Field definitions may still have stored columns. Read those too.
	columns = ["name"] + [prefix + field for field in (*SPEC_FIELDS, *LEGACY_FIELDS)
		if frappe.db.has_column(doctype, prefix + field)]
	selection = ", ".join(f"`{name}`" for name in columns)
	for row in frappe.db.sql(f"select {selection} from `tab{doctype}`", as_dict=True):
		values = legacy_spec_values(row, prefix)
		if values:
			frappe.db.set_value(doctype, row.name, values, update_modified=False)


def backfill_links():
	orders = {}
	by_product = defaultdict(list)
	sources = defaultdict(set)
	for item in frappe.get_all("Sales Order Item", filters={"parenttype": "Sales Order"},
		fields=["name", "parent", "item_code", "custom_part_list", *["custom_" + field for field in SPEC_FIELDS]]):
		orders[item.name] = item
		by_product[(item.parent, item.item_code)].append(item)
		if item.custom_part_list:
			sources[item.custom_part_list].add(item.name)
	requests = {row.name: row.sales_order for row in frappe.get_all("PDS Request", fields=["name", "sales_order"])}
	for row in frappe.get_all("PDS Request Item", filters={"parenttype": "PDS Request"},
		fields=["name", "parent", "item", "sales_order_item", "part_list", *SPEC_FIELDS]):
		order_name = requests.get(row.parent)
		matches = [item for item in by_product[(order_name, row.item)]
			if not row.sales_order_item or item.name == row.sales_order_item]
		if len(matches) != 1:
			continue
		item = matches[0]
		values = {field: value for field, value in spec_values(item, "custom_").items() if value and not row.get(field)}
		if not row.sales_order_item:
			values["sales_order_item"] = item.name
		if values:
			frappe.db.set_value("PDS Request Item", row.name, values, update_modified=False)
		if row.part_list:
			sources[row.part_list].add(item.name)
	for part in frappe.get_all("Part List", fields=["name", "product", "sales_order", "sales_order_item", *SPEC_FIELDS]):
		candidates = {part.sales_order_item} if part.sales_order_item else sources.get(part.name, set())
		if len(candidates) != 1:
			continue
		item = orders.get(next(iter(candidates)))
		if not item or item.item_code != part.product or (part.sales_order and part.sales_order != item.parent):
			continue
		values = {field: value for field, value in spec_values(item, "custom_").items() if value and not part.get(field)}
		values.update(sales_order=item.parent, sales_order_item=item.name)
		frappe.db.set_value("Part List", part.name, values, update_modified=False)
	for row in frappe.get_all("Project BOQ Item", filters={"parenttype": "Project"},
		fields=["name", "sales_order_item", "item_code"]):
		item = orders.get(row.sales_order_item)
		if item and item.item_code == row.item_code:
			frappe.db.set_value("Project BOQ Item", row.name, spec_values(item, "custom_"), update_modified=False)


def execute():
	# Patches run after model sync; after_migrate reapplies layouts after customizations.
	setup_fields()
	migrate_legacy("Sales Order Item", "custom_")
	migrate_legacy("PDS Request Item", "")
	backfill_links()
