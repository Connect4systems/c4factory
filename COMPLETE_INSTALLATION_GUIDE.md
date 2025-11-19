# Complete Installation Guide for c4factory App

## Current Status
✅ App installed successfully
❌ Custom fields not created yet (patches not run)
❌ Runtime error when creating Work Order

## The Issue
The error `AttributeError: 'NoneType' object has no attribute 'options'` occurs because the custom field `c4_required_items` doesn't exist yet in the Work Order doctype. This field is created by running database patches.

## Solution: Run Database Migration

### Step 1: Run Bench Migrate
This will apply all pending patches and create the custom fields:

```bash
cd ~/frappe-bench
bench --site develop.connect4systems.com migrate
```

Expected output:
```
Migrating develop.connect4systems.com
Executing c4factory.patches.v1_0.setup_work_order_custom_fields
Executing c4factory.patches.v1_0.setup_pick_list_custom_fields
Migration complete for develop.connect4systems.com
```

### Step 2: Clear Cache
After migration, clear the cache to ensure all changes are loaded:

```bash
bench --site develop.connect4systems.com clear-cache
```

### Step 3: Restart Bench
Restart all services to apply changes:

```bash
bench restart
```

### Step 4: Verify Custom Fields
Check if the custom fields were created:

```bash
bench --site develop.connect4systems.com console
```

Then in the console:
```python
import frappe
frappe.connect()

# Check Work Order custom fields
wo_meta = frappe.get_meta("Work Order")
c4_fields = [f.fieldname for f in wo_meta.fields if f.fieldname.startswith('c4_')]
print("Work Order C4 Fields:", c4_fields)

# Should show:
# ['c4_required_items_tab', 'c4_required_items', 'c4_items_section', 
#  'c4_total_picked_qty', 'c4_total_consumed_qty', 'c4_scrap_process_tab',
#  'c4_scrap_items', 'c4_process_loss_section', 'c4_process_loss_percent',
#  'c4_process_loss_qty', 'c4_costing_tab', 'c4_raw_material_cost',
#  'c4_operating_cost', 'c4_scrap_material_cost', 'c4_total_cost']

# Check Pick List custom fields
pl_meta = frappe.get_meta("Pick List")
c4_pl_fields = [f.fieldname for f in pl_meta.fields if f.fieldname.startswith('c4_')]
print("Pick List C4 Fields:", c4_pl_fields)

# Should show:
# ['c4_work_order', 'c4_status', 'c4_balance_section', 'c4_total_qty',
#  'c4_consumed_qty', 'c4_balance_qty']

exit()
```

### Step 5: Test Work Order Creation
Now try creating a Work Order again:

1. Go to: Work Order > New
2. Select a BOM
3. Enter quantity
4. Save

The Work Order should save successfully, and you should see:
- **C4 Required Items** tab with editable items from BOM
- **C4 Scrap & Process Loss** tab
- **C4 Costing** tab

## What the Patches Do

### Patch 1: setup_work_order_custom_fields
Creates custom fields in Work Order:
- `c4_required_items` - Editable table of required items (copied from BOM)
- `c4_total_picked_qty` - Total quantity picked in Pick Lists
- `c4_total_consumed_qty` - Total quantity consumed in Stock Entries
- `c4_scrap_items` - Scrap items table
- `c4_process_loss_percent` - Process loss percentage
- `c4_process_loss_qty` - Process loss quantity
- `c4_raw_material_cost` - Raw material cost
- `c4_operating_cost` - Operating cost
- `c4_scrap_material_cost` - Scrap material cost
- `c4_total_cost` - Total cost

### Patch 2: setup_pick_list_custom_fields
Creates custom fields in Pick List and Pick List Item:
- Pick List: `c4_work_order`, `c4_status`, `c4_total_qty`, `c4_consumed_qty`, `c4_balance_qty`
- Pick List Item: `c4_wo_required_qty`, `c4_balance_qty`, `c4_consumed_qty`

## Troubleshooting

### If migration fails:
```bash
# Check error logs
bench --site develop.connect4systems.com console

import frappe
frappe.connect()
frappe.db.sql("SELECT * FROM `tabPatch Log` WHERE patch LIKE '%c4factory%'")
```

### If custom fields don't appear:
```bash
# Force reload doctype
bench --site develop.connect4systems.com console

import frappe
frappe.connect()
frappe.clear_cache(doctype="Work Order")
frappe.clear_cache(doctype="Pick List")
frappe.clear_cache(doctype="Pick List Item")
frappe.clear_cache(doctype="Stock Entry")
```

### If you need to re-run patches:
```bash
# Delete patch log entries (use with caution!)
bench --site develop.connect4systems.com console

import frappe
frappe.connect()
frappe.db.sql("DELETE FROM `tabPatch Log` WHERE patch LIKE '%c4factory%'")
frappe.db.commit()

# Then run migrate again
exit()
bench --site develop.connect4systems.com migrate
```

## Complete Workflow After Migration

1. **Create Work Order**
   - Select BOM
   - Items are automatically copied to C4 Required Items tab
   - Edit quantities if needed
   - Submit Work Order

2. **Create Pick List from Work Order**
   - Open submitted Work Order
   - Click "Create Pick List" button
   - Pick List is created with items from c4_required_items
   - Submit Pick List

3. **Create Stock Entry from Pick List**
   - Open submitted Pick List
   - Click "Create Stock Entry" button
   - Stock Entry is created (Material Transfer for Manufacture)
   - Submit Stock Entry

4. **Track Progress**
   - Pick List shows consumed vs balance quantities
   - Work Order shows total picked and consumed quantities
   - Pick List status automatically updates (Open → Completed)

## Summary

The installation is complete, but you need to run `bench migrate` to create the custom fields. After migration, the app will work correctly.

**Quick Commands:**
```bash
cd ~/frappe-bench
bench --site develop.connect4systems.com migrate
bench --site develop.connect4systems.com clear-cache
bench restart
```

Then test by creating a new Work Order!
