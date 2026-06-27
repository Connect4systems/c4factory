// c4factory • Work Order — allow editing required_qty in items

frappe.ui.form.on("Work Order", {
  refresh(frm) {
    configure_required_items_grid(frm);
    set_missing_source_warehouses(frm);
    hide_create_job_card_button(frm);
  },
  onload_post_render(frm) {
    configure_required_items_grid(frm);
    hide_create_job_card_button(frm);
  },
  bom_no(frm) {
    setTimeout(() => set_missing_source_warehouses(frm), 800);
  },
  company(frm) {
    set_missing_source_warehouses(frm);
  },
  custom_disable_operation(frm) {
    hide_create_job_card_button(frm);
  }
});

frappe.ui.form.on("Work Order Item", {
  form_render(frm) {
    configure_required_items_grid(frm);
  },
  item_code(frm, cdt, cdn) {
    set_source_warehouse_from_item_group(frm, cdt, cdn);
  }
});

// Keep draft Work Order materials fully editable. ERPNext marks this grid as
// non-addable/non-deletable after populating it from the BOM.
function configure_required_items_grid(frm) {
  if (frm.doc.docstatus !== 0) return;

  // ERPNext v15 uses required_items; keep items as a compatibility fallback.
  const table_field =
    frm.fields_dict.required_items || frm.fields_dict.items;
  apply_required_items_grid_permissions(table_field);

  // Also fix the child DocType meta so newly added/rendered rows can select an
  // item and set its quantity.
  for (const fieldname of ["item_code", "required_qty", "source_warehouse"]) {
    const df = frappe.meta.get_docfield(
      "Work Order Item",
      fieldname,
      frm.doc.name
    );
    if (df) {
      df.read_only = 0;
    }
  }

  // Core Work Order refresh handlers can run after custom handlers and restore
  // the grid restrictions, so re-apply once the refresh cycle has settled.
  clearTimeout(frm.__c4_required_items_grid_timer);
  frm.__c4_required_items_grid_timer = setTimeout(() => {
    const current_field =
      frm.fields_dict.required_items || frm.fields_dict.items;
    if (frm.doc.docstatus !== 0) return;
    apply_required_items_grid_permissions(current_field);
  }, 0);
}

function apply_required_items_grid_permissions(table_field) {
  const grid = table_field && table_field.grid;
  if (!grid) return;

  table_field.df.read_only = 0;
  table_field.df.cannot_add_rows = 0;
  table_field.df.cannot_delete_rows = 0;

  grid.df.read_only = 0;
  grid.df.cannot_add_rows = 0;
  grid.df.cannot_delete_rows = 0;
  grid.cannot_add_rows = false;
  grid.cannot_delete_rows = false;

  for (const fieldname of ["item_code", "required_qty", "source_warehouse"]) {
    grid.update_docfield_property(fieldname, "read_only", 0);
    grid.toggle_enable(fieldname, true);
  }
  grid.refresh();
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

function hide_create_job_card_button(frm) {
  if (!frm.doc.custom_disable_operation) return;

  const remove_buttons = () => {
    frm.remove_custom_button(__("Job Card"), __("Create"));
    frm.remove_custom_button(__("Create Job Card"), __("Create"));
    frm.remove_custom_button(__("Create Job Card"));
  };

  remove_buttons();
  setTimeout(remove_buttons, 300);
  setTimeout(remove_buttons, 1000);
}
