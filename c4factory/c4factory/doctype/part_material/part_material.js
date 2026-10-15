frappe.ui.form.on('Part Material', {
  setup(frm) {
    frm.set_query('color', () => ({filters: {palette: frm.doc.color_palette || ''}}));
  },
  color_palette(frm) { return frm.set_value('color', null); },
});
