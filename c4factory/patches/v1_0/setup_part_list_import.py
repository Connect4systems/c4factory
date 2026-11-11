"""Initialize mapping metadata for pre-existing linked accessories, once per row.

The existing Item link and quantity remain authoritative. No historical mapping
user/date is invented. Re-running after_migrate leaves initialized rows alone.
"""
import frappe


def execute():
    frappe.db.sql("""
        update `tabAccessorise Table` a
        inner join `tabItem` i on i.name = a.item
        set a.requested_name = ifnull(nullif(a.requested_name, ''), i.item_name),
            a.requested_uom = i.stock_uom,
            a.stock_uom = i.stock_uom,
            a.conversion_factor = 1,
            a.stock_qty = a.qty,
            a.mapping_status = 'Matched'
        where ifnull(a.item, '') != ''
            and ifnull(a.stock_uom, '') = ''
            and ifnull(a.requested_uom, '') = ''
            and ifnull(a.conversion_factor, 0) in (0, 1)
    """)
