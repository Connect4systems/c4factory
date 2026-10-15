frappe.ui.form.on('Part Material', {
  setup(frm) {
    if (frm.fields_dict.color) frm.set_query('color', () => ({filters: {palette: frm.doc.color_palette || ''}}));
  },
  color_palette(frm) {
    if (frm.fields_dict.color) return frm.set_value('color', null);
  },
});
