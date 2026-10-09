// c4napata/public/js/doctype/sales_order/request_bom.js
frappe.ui.form.on('Sales Order', {
  setup(frm) {
    configureSalesOrderPartListQueries(frm);
  },
  items_on_form_rendered(frm) {
    const row = frm.cur_grid?.doc;
    if (row?.doctype === 'Sales Order Item') return syncSalesOrderColors(frm, row.doctype, row.name);
  },
  onload_post_render(frm) {
    configureSalesOrderPartListQueries(frm);
    if (frm.doc.docstatus !== 0) return;
    return Promise.all((frm.doc.items || []).map(row =>
      setSalesOrderDefaultPartList(frm, row.doctype, row.name, false)
        .then(() => syncSalesOrderColors(frm, row.doctype, row.name))
    ));
  },
  refresh(frm) {
    configureSalesOrderPartListQueries(frm);
    if (frm.doc.docstatus === 1 && frappe.model.can_create('Color sample')) {
      frm.add_custom_button(__('Color Sample'), () => openSalesOrderColorSample(frm), __('Create'));
    }
    if (!frm.is_new()) {
      frm.add_custom_button(__('Request PDS'), async () => {
        if (frm.is_dirty()) await frm.save();
        if (frm.is_dirty()) return;
        const result = await frappe.call({
          method: 'c4factory.api.pds_request.make_pds_request',
          args: { sales_order: frm.doc.name },
          freeze: true,
        });
        if (!result.message) return;
        const doc = frappe.model.sync(result.message)[0];
        frappe.set_route('Form', doc.doctype, doc.name);
      }, __('Create'));
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

function salesOrderPartListFields(frm) {
  return (frm.fields_dict.items?.grid?.docfields || []).filter(field =>
    field.fieldtype === 'Link' && field.options === 'Part List'
  ).map(field => field.fieldname);
}

function configureSalesOrderPartListQueries(frm) {
  for (const field of salesOrderPartListFields(frm)) {
    frm.set_query(field, 'items', (doc, cdt, cdn) => ({
      filters: {
        product: locals[cdt]?.[cdn]?.item_code || '',
        disable: 0,
        docstatus: 1,
      },
    }));
  }
}

async function setSalesOrderDefaultPartList(frm, cdt, cdn, clear) {
  const row = locals[cdt]?.[cdn];
  const fields = salesOrderPartListFields(frm);
  if (!row || !fields.length) return;
  const item = row.item_code;
  const request = { applying: true, cancelled: false };
  salesOrderPartListRequests.set(row, request);
  if (clear) {
    for (const field of fields) await frappe.model.set_value(cdt, cdn, field, null);
  }
  request.applying = false;
  if (!item || salesOrderPartListRequests.get(row) !== request || row.item_code !== item ||
      fields.every(field => row[field])) return;
  const partLists = await frappe.db.get_list('Part List', {
    fields: ['name'],
    filters: { product: item, is_default: 1, disable: 0, docstatus: 1 },
    order_by: 'name asc',
    limit: 1,
  });
  if (salesOrderPartListRequests.get(row) !== request || request.cancelled ||
      row.item_code !== item || locals[cdt]?.[cdn] !== row || !partLists.length) return;
  request.applying = true;
  try {
    for (const field of fields) {
      if (!row[field]) await frappe.model.set_value(cdt, cdn, field, partLists[0].name);
    }
  } finally {
    request.applying = false;
  }
}

function cancelSalesOrderPartListLookup(frm, cdt, cdn) {
  const row = locals[cdt]?.[cdn];
  const request = row && salesOrderPartListRequests.get(row);
  if (request && !request.applying) request.cancelled = true;
}

frappe.ui.form.on('Sales Order Item', {
  item_code(frm, cdt, cdn) {
    return setSalesOrderDefaultPartList(frm, cdt, cdn, true);
  },
  custom_part_list: cancelSalesOrderPartListLookup,
  part_list: cancelSalesOrderPartListLookup,
});


async function openSalesOrderColorSample(frm) {
  const response = await frappe.call({
    method: 'c4factory.api.color_sample.get_available_items',
    args: { sales_order: frm.doc.name },
  });
  const items = response.message || [];
  const esc = frappe.utils.escape_html;
  const dialog = new frappe.ui.Dialog({
    title: __('Create Color Sample'), size: 'extra-large',
    fields: [{ fieldname: 'items_html', fieldtype: 'HTML' }],
    primary_action_label: __('Create'),
    primary_action: async () => {
      const selections = [];
      let invalid = false;
      dialog.fields_dict.items_html.$wrapper.find('tbody tr').each(function () {
        if (!$(this).find('.sample-select').prop('checked')) return;
        const index = Number($(this).attr('data-index'));
        const item = items[index];
        const qty = Number($(this).find('.sample-qty').val());
        if (!Number.isFinite(qty) || qty <= 0 || qty > Number(item.remaining_qty)) {
          invalid = true;
          return;
        }
        selections.push({ sales_order_item: item.sales_order_item, qty });
      });
      if (invalid) { frappe.msgprint(__('Enter a positive quantity within the available balance.')); return; }
      if (!selections.length) { frappe.msgprint(__('Select at least one item.')); return; }
      dialog.get_primary_btn().prop('disabled', true);
      try {
        const result = await frappe.call({
          method: 'c4factory.api.color_sample.make_color_sample',
          args: { sales_order: frm.doc.name, selections: JSON.stringify(selections) },
          freeze: true,
        });
        if (!result.message) return;
        const doc = frappe.model.sync(result.message)[0];
        dialog.hide();
        frappe.set_route('Form', doc.doctype, doc.name);
      } finally { dialog.get_primary_btn().prop('disabled', false); }
    },
  });
  dialog.fields_dict.items_html.$wrapper.html(`
    <p class="text-muted">${__('Only submitted Color Samples reduce the available quantity. Cancelled samples release their quantity.')}</p>
    <div style="overflow:auto"><table class="table table-bordered">
    <thead><tr><th>${__('Select')}</th><th>${__('Row')}</th><th>${__('Item')}</th><th>${__('Part List')}</th><th>${__('Order Qty')}</th><th>${__('Sampled Qty')}</th><th>${__('Available Qty')}</th><th>${__('Quantity')}</th></tr></thead>
    <tbody>${items.map((item, index) => {
      const enabled = Number(item.remaining_qty) > 0 && item.part_list;
      return `<tr data-index="${index}">
        <td><input class="sample-select" type="checkbox" ${enabled ? '' : 'disabled'}></td>
        <td>${index + 1}</td><td>${esc(item.item_code)}<br>${esc(item.item_name || '')}</td>
        <td>${esc(item.part_list || __('No Part List'))}</td>
        <td>${Number(item.order_qty)}</td><td>${Number(item.submitted_qty)}</td><td>${Number(item.remaining_qty)}</td>
        <td><input class="form-control sample-qty" type="number" min="0" step="any" max="${Number(item.remaining_qty)}" value="${Number(item.remaining_qty)}" ${enabled ? '' : 'disabled'}></td>
      </tr>`;
    }).join('')}</tbody></table></div>`);
  dialog.show();
}
