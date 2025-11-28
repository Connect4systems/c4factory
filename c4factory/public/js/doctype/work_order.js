// c4factory • Work Order — allow editing required_qty in items

frappe.ui.form.on("Work Order", {
  refresh(frm) {
    make_required_qty_editable(frm);
  },
  onload_post_render(frm) {
    make_required_qty_editable(frm);
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
