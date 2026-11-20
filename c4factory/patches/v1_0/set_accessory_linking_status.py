"""Populate the derived linking status without changing submitted technical data."""

import frappe


def execute():
    frappe.db.sql("""
        update `tabPart List` p
        left join (
            select parent, count(*) as total,
                sum(case when coalesce(item, '') != '' then 1 else 0 end) as mapped
            from `tabAccessorise Table`
            where parenttype = 'Part List' and parentfield = 'accessorise_table'
            group by parent
        ) a on a.parent = p.name
        set p.accessory_linking_status = case
            when coalesce(a.total, 0) = coalesce(a.mapped, 0) then 'Completed'
            when a.mapped > 0 then 'Partly Linked'
            else 'Pending Linking'
        end
    """)
