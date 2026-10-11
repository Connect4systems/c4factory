frappe.ui.form.on('Color sample', {
  refresh(frm) {
    // Validation already saves the colors. Refresh must leave a saved draft clean.
    for (const row of frm.doc.items || []) {
      renderSalesOrderColors(frm, row.doctype, row.name);
    }
  },
  items_on_form_rendered(frm) {
    const row = frm.cur_grid?.doc;
    if (row?.doctype === 'Color Sample Item') return syncSalesOrderColors(frm, row.doctype, row.name);
  },
});
