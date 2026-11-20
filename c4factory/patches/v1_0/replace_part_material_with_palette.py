"""Preserve palette assignments before retiring Part Material links."""

import frappe


def execute():
    if frappe.db.table_exists("Part Material"):
        for table in ("Part List Materials", "Color Sample Table"):
            frappe.db.sql(f"""
                update `tab{table}` r
                inner join `tabPart Material` m on m.name = r.material
                set r.color_palette = m.color_palette
                where coalesce(r.color_palette, '') = ''
                    and coalesce(m.color_palette, '') != ''
            """)
    frappe.db.sql("""
        update `tabPart List Materials` r
        inner join `tabMaterial Color` c on c.name = r.basic_color
        set r.color_palette = c.palette
        where coalesce(r.color_palette, '') = ''
    """)
    # Only homogeneous sections get a header; mixed historical rows stay intact.
    for table, prefix in (("panel_materials", "panel"), ("metal_material", "metal"), ("other_material", "other")):
        frappe.db.sql(f"""
            update `tabPart List` p
            inner join (
                select parent, min(color_palette) as palette,
                    case when count(distinct coalesce(basic_color, '')) = 1
                        then min(basic_color) else null end as base_color
                from `tabPart List Materials`
                where parenttype = 'Part List' and parentfield = %(table)s
                group by parent
                having count(distinct coalesce(color_palette, '')) = 1
            ) r on r.parent = p.name
            set p.{prefix}_color_palette = r.palette,
                p.{prefix}_base_color = r.base_color
            where coalesce(p.{prefix}_color_palette, '') = ''
                and coalesce(p.{prefix}_base_color, '') = ''
        """, {"table": table})
