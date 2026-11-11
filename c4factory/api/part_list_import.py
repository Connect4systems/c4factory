"""Bounded spreadsheet reading and deterministic Part List import previews.

Workbook contents are data only. Never execute macros or formulas.
"""
import csv
import io
import json
import math

import frappe
from frappe import _

TABLES = ("panel_materials", "metal_material", "other_material", "accessorise_table")
FIELDS = ("part_name", "part_name_ar", "material", "lenght", "width", "hight", "thickness", "qty", "note", "requested_name")
MAX_ROWS = 3000
MAX_COLUMNS = 60


@frappe.whitelist()
def download_template(table):
    if table not in TABLES or not frappe.has_permission("Part List", "create"):
        frappe.throw(_("Invalid table or insufficient permissions."))
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    sheet.title = "Import"
    sheet.append(["Requested Item Name", "Qty", "Notes"] if table == "accessorise_table" else
        ["Part Name English", "Part Name Arabic", "Length", "Width", "Height", "Thickness", "Qty", "Material", "Notes"])
    output = io.BytesIO()
    book.save(output)
    frappe.response["filename"] = f"{table}_template.xlsx"
    frappe.response["filecontent"] = output.getvalue()
    frappe.response["type"] = "binary"


def read_workbook(content, filename):
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Maximum workbook size is 10 MB.")
    result = {}
    if filename.lower().endswith(".xls"):
        import xlrd
        book = xlrd.open_workbook(file_contents=content, on_demand=True)
        try:
            for sheet in book.sheets():
                if sheet.nrows > MAX_ROWS or sheet.ncols > MAX_COLUMNS:
                    raise ValueError("Sheet exceeds 3,000 rows or 60 columns.")
                result[sheet.name] = [sheet.row_values(r) for r in range(sheet.nrows)]
        finally:
            book.release_resources()
    elif filename.lower().endswith(".xlsx"):
        from openpyxl import load_workbook
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            for sheet in book:
                if sheet.max_row > MAX_ROWS or sheet.max_column > MAX_COLUMNS:
                    raise ValueError("Sheet exceeds 3,000 rows or 60 columns.")
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    rows.append([v if isinstance(v, (str, int, float)) else "" for v in row])
                result[sheet.title] = rows
        finally:
            book.close()
    else:
        raise ValueError("Choose an .xls or .xlsx workbook.")
    return result


def parse_paste(text):
    return list(csv.reader(io.StringIO(text), delimiter="\t"))


def build_preview(matrix, mapping, table, material="", start_row=1, end_row=None):
    if table not in TABLES or not isinstance(matrix, list) or not isinstance(mapping, dict):
        raise ValueError("Invalid import configuration.")
    if len(matrix) > MAX_ROWS or any(not isinstance(r, list) or len(r) > MAX_COLUMNS for r in matrix):
        raise ValueError("Maximum 3,000 rows and 60 columns.")
    if any(k not in FIELDS or not isinstance(v, int) or v < 0 or v >= MAX_COLUMNS for k, v in mapping.items()):
        raise ValueError("Invalid column mapping.")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("A source column may only be mapped once.")
    required = ("requested_name", "qty") if table == "accessorise_table" else ("part_name", "part_name_ar", "qty")
    if any(k not in mapping for k in required):
        raise ValueError("Map all required name and quantity columns.")
    allowed = {"requested_name", "qty", "note"} if table == "accessorise_table" else set(FIELDS) - {"requested_name"}
    if not set(mapping) <= allowed:
        raise ValueError("Columns do not belong to the selected table.")
    start, end = int(start_row), int(end_row or len(matrix))
    if start < 1 or end < start or end > len(matrix):
        raise ValueError("Invalid row range.")
    result = []
    for index in range(start - 1, end):
        source = matrix[index]
        values = {k: str(source[c] if c < len(source) and source[c] is not None else "").strip() for k, c in mapping.items()}
        if not any(values.values()):
            continue
        errors = []
        for key in required:
            if not values.get(key):
                errors.append(f"{key} is required")
        if table != "accessorise_table":
            values["material"] = values.get("material") or material
            if not values["material"]:
                errors.append("Select a material")
        for key in ("qty", "lenght", "width", "hight", "thickness"):
            if key not in values:
                continue
            raw = values[key]
            if not raw and key != "qty":
                values[key] = None
                continue
            try:
                value = float(raw)
                if not math.isfinite(value) or value < 0 or (key == "qty" and value == 0):
                    raise ValueError
                values[key] = value
            except (TypeError, ValueError):
                errors.append(f"{key} must be a {'positive' if key == 'qty' else 'non-negative'} number")
        result.append({"source_row": index + 1, "values": values, "errors": errors})
    return result


@frappe.whitelist()
def inspect_workbook(file_url):
    if not frappe.has_permission("Part List", "create"):
        frappe.throw(_("You do not have permission to import Part Lists."), frappe.PermissionError)
    file = frappe.get_doc("File", {"file_url": file_url})
    file.check_permission("read")
    try:
        return read_workbook(file.get_content(), file.file_name)
    except (ValueError, OSError) as exc:
        frappe.throw(str(exc))


@frappe.whitelist()
def preview_import(matrix, mapping, table, material="", start_row=1, end_row=None):
    if not frappe.has_permission("Part List", "create"):
        frappe.throw(_("You do not have permission to import Part Lists."), frappe.PermissionError)
    try:
        return build_preview(json.loads(matrix) if isinstance(matrix, str) else matrix,
            json.loads(mapping) if isinstance(mapping, str) else mapping, table, material, start_row, end_row)
    except (ValueError, TypeError) as exc:
        frappe.throw(str(exc))
