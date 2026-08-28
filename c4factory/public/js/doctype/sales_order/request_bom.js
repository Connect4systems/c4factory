// c4napata/public/js/doctype/sales_order/request_bom.js
frappe.ui.form.on('Sales Order', {
  refresh(frm) {
    if (!frm.is_new()) {
      frm.add_custom_button(__('Request BOM'), async () => {
        // The mapper runs on the server, so save any specification changes first.
        // Otherwise it would read the previous values from the database.
        if (frm.is_dirty()) {
          await frm.save();
        }

        if (frm.is_dirty()) return;

        frappe.call({
          method: 'c4factory.api.contract_bom.make_contract_bom_request',
          args: { sales_order: frm.doc.name },
          freeze: true,
          callback: (r) => {
            if (!r.message) return;
            const doc = frappe.model.sync(r.message)[0]; // local unsaved doc
            frappe.set_route('Form', doc.doctype, doc.name);
          }
        });
      }, __('Create'));
    }
  }
});
