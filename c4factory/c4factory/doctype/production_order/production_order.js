frappe.ui.form.on('Production Order', {
  refresh(frm) {
    if (!frm.doc.color_sample) return;
    frm.add_custom_button(__('Color Sample'), () =>
      frappe.set_route('Form', 'Color sample', frm.doc.color_sample), __('View'));
    if (frm.doc.part_list) {
      frm.add_custom_button(__('Source Part List'), () =>
        frappe.set_route('Form', 'Part List', frm.doc.part_list), __('View'));
    }
  },
});
