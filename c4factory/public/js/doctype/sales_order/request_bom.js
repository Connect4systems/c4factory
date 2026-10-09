// c4napata/public/js/doctype/sales_order/request_bom.js
frappe.ui.form.on('Sales Order', {
  setup(frm) {
    configureSalesOrderPartListQueries(frm);
  },
  onload_post_render(frm) {
    configureSalesOrderPartListQueries(frm);
    if (frm.doc.docstatus !== 0) return;
    return Promise.all((frm.doc.items || []).map(row =>
      setSalesOrderDefaultPartList(frm, row.doctype, row.name, false)
    ));
  },
  refresh(frm) {
    configureSalesOrderPartListQueries(frm);
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

// Sales Order Item is a child DocType: store selections as JSON and render
// native Dynamic Link controls instead of an unsupported nested child table.
const salesOrderColorRequests = new WeakMap();

async function renderSalesOrderColors(frm, cdt, cdn) {
  const item = locals[cdt]?.[cdn];
  const gridRow = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[cdn];
  const wrapper = gridRow?.grid_form?.fields_dict.custom_color_sample_table?.$wrapper;
  if (!item || !wrapper) return;
  const partList = item.custom_part_list || item.part_list;
  const request = {};
  salesOrderColorRequests.set(item, request);
  wrapper.empty();
  if (!partList) return;
  wrapper.text(__('Loading colors…'));
  let result;
  try {
    result = await frappe.call({
      method: 'c4factory.api.sales_order_colors.get_color_rows',
      args: { part_list: partList },
    });
  } catch (error) {
    if (salesOrderColorRequests.get(item) === request) wrapper.text(__('Unable to load colors. Reopen this item to retry.'));
    throw error;
  }
  if (salesOrderColorRequests.get(item) !== request || locals[cdt]?.[cdn] !== item ||
      (item.custom_part_list || item.part_list) !== partList) return;
  let saved = {};
  try { saved = JSON.parse(item.custom_color_sample_data || '{}'); } catch { /* Rebuild invalid data. */ }
  const choices = new Map((saved.part_list === partList && Array.isArray(saved.rows) ? saved.rows : [])
    .filter(row => row && typeof row === 'object').map(row => [row.source_row, row]));
  const rows = (result.message || []).map(source => {
    const choice = choices.get(source.source_row);
    return { ...source, color: !source.color_doctype ? null :
      choice?.color_doctype === source.color_doctype ? choice.color : source.color };
  });
  const esc = frappe.utils.escape_html;
  wrapper.html(`<h6>${__('Color Sample Table')}</h6>`);
  if (!rows.length) {
    wrapper.append($('<p class="text-muted">').text(__('No materials with Edite Color enabled.')));
    return;
  }
  const table = $(`<table class="table table-bordered"><thead><tr><th>${__('Material')}</th><th>${__('Part Name')}</th><th>${__('Color')}</th></tr></thead><tbody></tbody></table>`).appendTo(wrapper);
  for (const row of rows) {
    const tr = $(`<tr><td>${esc(row.material || '')}</td><td>${esc(row.part_name || '')}</td><td></td></tr>`).appendTo(table.find('tbody'));
    const control = frappe.ui.form.make_control({
      parent: tr.find('td').last(),
      df: {
        fieldname: 'color', fieldtype: 'Dynamic Link', options: 'color_doctype',
        label: __('Color'), read_only: !row.color_doctype || frm.doc.docstatus !== 0 || frm.read_only,
        onchange: () => {
          if (salesOrderColorRequests.get(item) !== request ||
              (item.custom_part_list || item.part_list) !== partList) return;
          row.color = control.get_value() || null;
          frappe.model.set_value(cdt, cdn, 'custom_color_sample_data', JSON.stringify({ part_list: partList, rows }));
        },
      },
      doc: row,
      render_input: true,
    });
    control.set_input(row.color || '');
  }
}

frappe.ui.form.on('Sales Order Item', {
  form_render: renderSalesOrderColors,
  custom_part_list(frm, cdt, cdn) {
    return renderSalesOrderColors(frm, cdt, cdn);
  },
  part_list(frm, cdt, cdn) {
    return renderSalesOrderColors(frm, cdt, cdn);
  },
});
