# Project BOQ workflow

Sales Order submission creates a Project whose document ID is the trimmed Project No,
whose title is `Project No – Customer Name`, and whose customer, company, Technical Team,
expected start date and expected end date come from the order. Start uses transaction
date; end uses header delivery date. Project No collisions fail the submission transaction.
Retries and amendments reuse the matching Project. Existing matching Projects retain
their IDs to preserve existing references.

The Project BOQ tab has one row per Sales Order item, including repeated item codes.
Actual Qty means ordered quantity in the order row's UOM. Delivered quantity is submitted
Delivery Note stock quantity, net of submitted returns, converted to that UOM. Installed
quantity comes from submitted Installation Notes referencing those delivery rows.
Drafts and cancelled documents do not count. All delivered units can be fully installed
while the order is still partly delivered.

PDS progress uses the Item Type's BOQ Required flag. Submitted enabled Part Lists linked
to an order row take precedence over active PDS Requests for the item. The grid displays
the document number; expanded rows include clickable Part List and PDS Request links.

Select BOQ rows and choose Create Delivery Note, or expand one row and choose Create
Delivery. Enter partial quantities in the dialog. Only selected rows with positive
quantities are included. ERPNext's standard order mapping, pricing, taxes, packing and
stock validations remain in use. The saved draft opens for review; it is not submitted.
An existing draft for a selected order row must be reviewed or deleted first.

Expand a BOQ row and choose Create Installation Note to see submitted delivery rows
with remaining installation quantity. Quantities in that dialog use each delivery
row's UOM. The standard ERPNext Installation Note is reused. Serial numbers and other
required installation details can be completed on the draft before submission.
Server validation checks the delivery, customer, company, item, Project, returns and
previously installed quantity, including repeated references within one note.

Delivery or installation creation requires an active submitted order and the user's
normal document permissions. Returns or delivery cancellation affecting installed rows
require cancelling the related Installation Notes first. Cancelling a return remains
allowed. Historic transaction documents remain available when an order is amended;
the Project's current BOQ follows the replacement order.

Progress recalculates on Project load and through Refresh BOQ. Transaction hooks also
persist derived BOQ rows for reporting without changing the Project's modified timestamp.
The grid's counters are read-only and rebuilt on Project save.

## Deployment

Run from the Frappe bench after deploying this app version:

```sh
bench --site <site-name> migrate
bench build --app c4factory
bench --site <site-name> clear-cache
```

Migration creates the Project fields and Installation Note Project link. The Project
BOQ Item child DocType is synchronized from app metadata. No additional installation
DocType is required. Existing Projects gain a live BOQ when opened.

Sites with an existing Float `Project.custom_project_no` receive a targeted conversion
to Data through Frappe's schema updater. Existing numeric values are retained; text
project numbers become supported. Only this known conversion bypasses Custom Field
type-change validation. The patch can be rerun after a failed migration.

## Site acceptance checks

1. Submit an order with a unique Project No, two rows with the same item code, dates
   and Technical Team. Check Project identity, title, fields and separate BOQ rows.
2. Select one row and create a partial delivery draft. Confirm excluded rows are absent,
   taxes and any product bundle packing are correct, and progress changes on submission.
3. Create a partial installation against that delivery. Supply serial numbers if needed,
   submit, and confirm delivered and installed quantities and statuses.
4. Verify excessive installation quantities and duplicate draft creation are rejected.
5. Cancel the installation, return part of the delivery, then cancel the return. Check
   quantities after each step. Check that installed deliveries cannot be returned first.
6. Cancel and amend an eligible order. Confirm the matching Project is reused and its
   BOQ follows the amended order. Check PDS Request and submitted Part List links.
