"""Validate the native Item UOM table used by ERPNext transactions."""

import math

import frappe
from frappe import _


def validate_item_uoms(doc, method=None):
	seen = set()
	for row in doc.get("uoms") or []:
		if not row.uom:
			frappe.throw(_("Row {0}: Select a UOM.").format(row.idx))
		if row.uom in seen:
			frappe.throw(_("Row {0}: UOM {1} is already listed for this item.").format(row.idx, row.uom))
		seen.add(row.uom)
		try:
			factor = float(row.conversion_factor or 0)
		except (TypeError, ValueError):
			factor = 0
		if not math.isfinite(factor) or factor <= 0:
			frappe.throw(_("Row {0}: Conversion Factor must be a positive number.").format(row.idx))
		if row.uom == doc.stock_uom and factor != 1:
			frappe.throw(_("Row {0}: Conversion Factor for the Default UOM must be 1.").format(row.idx))
	for fieldname in ("purchase_uom", "sales_uom"):
		uom = doc.get(fieldname)
		if uom and uom != doc.stock_uom and uom not in seen:
			frappe.throw(_("Add UOM {0} and its conversion factor to this item's UOM table.").format(uom))
