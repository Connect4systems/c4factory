// c4napata/public/js/doctype/sales_order/request_bom.js
frappe.ui.form.on('Sales Order', {
  setup(frm) {
    frm.set_query('custom_part_list', 'items', (doc, cdt, cdn) => ({
      filters: {
        product: locals[cdt][cdn].item_code || '',
        disable: 0,
        docstatus: ['!=', 2],
      },
    }));
  },
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

// Each row keeps its own request so delayed responses cannot replace a manual choice.
const salesOrderPartListRequests = new WeakMap();

frappe.ui.form.on('Sales Order Item', {
  async item_code(frm, cdt, cdn) {
    const row = locals[cdt]?.[cdn];
    if (!row) return;
    const item = row.item_code;
    const request = { applying: true, cancelled: false };
    salesOrderPartListRequests.set(row, request);
    await frappe.model.set_value(cdt, cdn, 'custom_part_list', null);
    request.applying = false;
    if (!item || salesOrderPartListRequests.get(row) !== request || row.item_code !== item) return;

    const partLists = await frappe.db.get_list('Part List', {
      fields: ['name'],
      filters: { product: item, is_default: 1, disable: 0, docstatus: ['!=', 2] },
      order_by: 'name asc',
      limit: 1,
    });
    if (salesOrderPartListRequests.get(row) !== request || request.cancelled ||
        row.item_code !== item || locals[cdt]?.[cdn] !== row || row.custom_part_list) return;
    request.applying = true;
    try {
      await frappe.model.set_value(cdt, cdn, 'custom_part_list', partLists[0]?.name || null);
    } finally {
      request.applying = false;
    }
  },
  custom_part_list(frm, cdt, cdn) {
    const row = locals[cdt]?.[cdn];
    const request = row && salesOrderPartListRequests.get(row);
    if (request && !request.applying) request.cancelled = true;
  },
});
