frappe.ui.form.on('Color sample', {
  refresh(frm) {
    if (frm.doc.docstatus === 1 && frappe.model.can_create('Production Order')) {
      frm.add_custom_button(__('Production Order'), () => openSampleProductionOrder(frm), __('Create'));
    }
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

async function openSampleProductionOrder(frm) {
  const response = await frappe.call({
    method: 'c4factory.api.production_order.get_available_items',
    args: { color_sample: frm.doc.name },
  });
  const items = (response.message || []).filter(row => Number(row.remaining_qty) > 0);
  if (!items.length) {
    frappe.msgprint(__('All Color Sample quantities have already been allocated to submitted Production Orders.'));
    return;
  }
  const byName = new Map(items.map(row => [row.color_sample_item, row]));
  const esc = frappe.utils.escape_html;
  let dialog;
  function showBalance() {
    if (!dialog) return;
    const row = byName.get(dialog.get_value('color_sample_item'));
    if (!row) return;
    dialog.fields_dict.balance.$wrapper.html(
      `<p>${__('Sample Quantity')}: <strong>${Number(row.sample_qty)}</strong><br>` +
      `${__('Previously Ordered')}: <strong>${Number(row.ordered_qty)}</strong><br>` +
      `${__('Available Quantity')}: <strong>${Number(row.remaining_qty)} ${esc(row.uom || '')}</strong></p>`
    );
    dialog.set_value('qty', Number(row.remaining_qty));
  }
  dialog = new frappe.ui.Dialog({
    title: __('Create Production Order'),
    fields: [
      { fieldname: 'color_sample_item', fieldtype: 'Select', label: __('Product'), reqd: 1,
        options: items.map((row, index) => ({ value: row.color_sample_item,
          label: `${row.item_code} - ${row.item_name || ''} (${__('Row')} ${index + 1})` })),
        default: items[0].color_sample_item, onchange: showBalance },
      { fieldname: 'balance', fieldtype: 'HTML' },
      { fieldname: 'qty', fieldtype: 'Float', label: __('Production Quantity'), reqd: 1,
        default: Number(items[0].remaining_qty) },
    ],
    primary_action_label: __('Create'),
    primary_action: async values => {
      const row = byName.get(values.color_sample_item);
      const qty = Number(values.qty);
      if (!row || !Number.isFinite(qty) || qty <= 0 || qty > Number(row.remaining_qty)) {
        frappe.msgprint(__('Enter a positive production quantity within the available balance.'));
        return;
      }
      dialog.disable_primary_action();
      try {
        const result = await frappe.call({
          method: 'c4factory.api.production_order.make_production_order',
          args: { color_sample: frm.doc.name, color_sample_item: row.color_sample_item, qty },
          freeze: true,
        });
        if (!result.message) return;
        const doc = frappe.model.sync(result.message)[0];
        dialog.hide();
        frappe.set_route('Form', doc.doctype, doc.name);
      } finally { dialog.enable_primary_action(); }
    },
  });
  showBalance();
  dialog.show();
}
