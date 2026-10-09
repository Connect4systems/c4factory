frappe.ui.form.on('Color sample', {
  refresh(frm) {
    if (frm.doc.docstatus !== 0) return;
    return Promise.all((frm.doc.items || []).map(row =>
      syncSalesOrderColors(frm, row.doctype, row.name)));
  },
  items_on_form_rendered(frm) {
    const row = frm.cur_grid?.doc;
    if (row?.doctype === 'Color Sample Item') return syncSalesOrderColors(frm, row.doctype, row.name);
  },
});
