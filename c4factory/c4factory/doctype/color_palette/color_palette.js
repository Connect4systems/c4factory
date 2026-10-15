frappe.ui.form.on('Color Palette', {
  refresh(frm) {
    if (frm.is_new()) return;
    frm.add_custom_button(__('Color'), () => {
      frappe.route_options = { palette: frm.doc.name };
      frappe.set_route('List', 'Material Color');
    });
  },
});
