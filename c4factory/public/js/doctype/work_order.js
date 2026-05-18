// c4factory • Work Order — allow editing required_qty in items

frappe.ui.form.on("Work Order", {
  refresh(frm) {
    make_required_qty_editable(frm);
    set_missing_source_warehouses(frm);
  },
  onload_post_render(frm) {
    make_required_qty_editable(frm);
  },
  bom_no(frm) {
    setTimeout(() => set_missing_source_warehouses(frm), 800);
  },
  company(frm) {
    set_missing_source_warehouses(frm);
  }
});

frappe.ui.form.on("Work Order Item", {
  item_code(frm, cdt, cdn) {
    set_source_warehouse_from_item_group(frm, cdt, cdn);
  }
});

// helper: remove read_only from required_qty in child grid
function make_required_qty_editable(frm) {
  // for all rows already in the grid
  if (frm.fields_dict.required_items && frm.fields_dict.required_items.grid) {
    frm.fields_dict.required_items.grid.update_docfield_property(
      "required_qty",
      "read_only",
      0
    );
  }

  // also fix the meta definition so new rows are editable
  const df = frappe.meta.get_docfield(
    "Work Order Item",
    "required_qty",
    frm.doc.name
  );
  if (df) {
    df.read_only = 0;
  }
}

async function set_missing_source_warehouses(frm) {
  if (frm.doc.docstatus !== 0) return;

  const rows = frm.doc.required_items || frm.doc.items || [];
  for (const row of rows) {
    if (row.item_code && !row.source_warehouse) {
      await set_source_warehouse_from_item_group(frm, row.doctype, row.name);
    }
  }
}

async function set_source_warehouse_from_item_group(frm, cdt, cdn) {
  const row = locals[cdt] && locals[cdt][cdn];
  if (!row || !row.item_code || row.source_warehouse) return;

  const { message: warehouse } = await frappe.call({
    method: "c4factory.c4_manufacturing.work_order_hooks.get_default_source_warehouse",
    args: {
      item_code: row.item_code,
      item_group: row.item_group,
      company: frm.doc.company
    }
  });

  if (warehouse && !locals[cdt][cdn].source_warehouse) {
    await frappe.model.set_value(cdt, cdn, "source_warehouse", warehouse);
  }
}
