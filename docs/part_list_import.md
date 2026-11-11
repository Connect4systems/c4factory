# Part List spreadsheet import and accessory mapping

Deploy the app with its Python dependencies, then run:

```sh
bench setup requirements --python
bench --site <site> migrate
bench build --app c4factory
```

Migration syncs the new child fields, changes `part_name` from Link to Data while
retaining its English text, grants stock roles read access to Part Lists, and
initializes mapping metadata for existing linked accessories. Existing material
rows are not forced to acquire Arabic translations on their next save. New rows
require English and Arabic names. The old Part Name master is retained.

## Importing

In an editable draft, choose **Import / Paste → table name**. Paste a rectangular
Excel range or upload `.xls` / `.xlsx` (10 MB maximum). Choose one workbook sheet.
Uploads populate **Part File** on the Part List. Save the Part List to retain
that attachment; subsequent imports load it automatically, without another
upload. A pasted range takes priority over the attached workbook. Uploading a
replacement workbook updates Part File after the workbook is read successfully.
The supplied `Part L.` layout has suggested column mappings and section ranges;
other sheets can be mapped manually. Source contents never execute as code.

When the sheet or pasted range contains section headers, first select **Excel
Section Header**, then **Import into Table**, then **Part Material for this
Section**. Wooden Panel / Panel / Material suggest Panel Materials; Metal, Other,
and Accessories suggest their corresponding tables. The destination is editable.
The section's row range is filled automatically, stopping at the next section;
accessory column headings and document footers are excluded. Column mappings are
shown vertically in the next step. Choose Whole sheet / pasted rows to set the
range manually instead.

The template download provides a plain `.xlsx` header row. Pasted names are text;
no Part Name masters or Item masters are created. Material defaults can be applied
to a whole import and overridden through a mapped Material column. These values
must reference existing Part Materials. Quantity must be positive; unused
dimensions remain blank. Column mappings are remembered in this browser when
storage is available.

The preview shows source row numbers and errors. Invalid rows cannot be included.
The selected section material carries through mapping and preview. The preview
material repair controls appear only when rows still have no material.
Adding imported rows removes untouched empty starter rows, preserving existing
rows that contain entered data.
If no Material column is mapped, a Part Material must be chosen before opening
the preview. Click a valid row or its checkbox to toggle inclusion, or use
**Select All Valid Rows** / **Deselect All**. **Back to Mapping** returns to the
column and material settings to correct errors.
Possible `Drawer Unit` assembly rows start unchecked so the user can decide
whether to count the assembly alongside its components. **Add Rows** is the
default; **Replace Table Rows** must be explicitly selected. Nothing is persisted
until the Part List is saved. Uploads remain private File records.

For the supplied desk file, prefer `Part L.` over `BOM List`: the latter lacks
Arabic names, puts metal height values under Thickness, and repeats components
from the other sheets. Import one source sheet, never all sheets together.

## Accessory mapping

Accessories accept Requested Item Name, Qty, and optional Notes without an Item
code. A technical Part List can be submitted with pending accessories.

On a submitted Part List, Stock User, Stock Manager, or System Manager can use
**Map Accessories**. The selected Item must be an enabled stock Item without
variants and readable by the user. A blank Requested UOM means the stock UOM;
otherwise its conversion must match the Item's configured UOM conversion.
Stock quantity is requested quantity × conversion factor. Whole-number stock
UOMs are enforced. The requested name, quantity and notes remain unchanged, and
mapping user/time are server generated.

Submitted technical fields and table rows are locked. Changes to the design need
a new version. Mapping edits also require a new version once a non-cancelled
Production Order snapshots that Part List. Production Order creation and
validation reject unmapped accessories. Other apps' independent stock workflows
are not changed; this repository's Part List consumption goes through the
Production Order snapshot.

## Validation

```sh
python -m unittest discover -s tests -p 'test_*.py'
python tests/part_list_import_ui.py --workbook /path/to/customer.xls
```

The browser test uses Playwright with Edge and a small Frappe adapter. It exercises
the real JavaScript dialogs and Python preview parser. It does not replace a
live-site migration and role-permission acceptance test.
