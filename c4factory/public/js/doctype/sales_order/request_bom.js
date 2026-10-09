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
        .then(() => syncSalesOrderColors(frm, row.doctype, row.name))
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

// Both views edit the same per-item data; the original Part List is read-only.
const salesOrderColorRequests = new WeakMap();
const salesOrderColorInitializing = new WeakSet();

function salesOrderStoredColors(item) {
  try {
    const data = JSON.parse(item.custom_color_sample_data || '{}');
    return data && Array.isArray(data.rows) ? data : { rows: [] };
  } catch { return { rows: [] }; }
}

async function syncSalesOrderColors(frm, cdt, cdn) {
  const item = locals[cdt]?.[cdn];
  if (!item) return;
  if (frm.doc.docstatus !== 0 || frm.read_only) {
    renderSalesOrderColors(frm, cdt, cdn);
    return;
  }
  const partList = item.custom_part_list || item.part_list;
  const request = {};
  salesOrderColorRequests.set(item, request);
  if (!partList) {
    salesOrderColorInitializing.add(item);
    try {
      await frappe.model.set_value(cdt, cdn, {
        custom_color_sample_data: null, custom_wood: null,
        custom_metal: null, custom_wood_color_doctype: null,
      });
    } finally { salesOrderColorInitializing.delete(item); }
    renderSalesOrderColors(frm, cdt, cdn);
    return;
  }
  const result = await frappe.call({
    method: 'c4factory.api.sales_order_colors.get_part_list_colors',
    args: { part_list: partList },
  });
  if (salesOrderColorRequests.get(item) !== request || locals[cdt]?.[cdn] !== item ||
      (item.custom_part_list || item.part_list) !== partList) return;
  const config = result.message;
  const saved = salesOrderStoredColors(item);
  const matching = saved.part_list === partList;
  const choices = new Map((matching ? saved.rows : [])
    .filter(row => row && typeof row === 'object').map(row => [row.source_row, row]));
  const rows = (config.rows || []).map(source => {
    const choice = choices.get(source.source_row);
    return { ...source, color: !source.color_doctype ? null :
      choice?.color_doctype === source.color_doctype ? choice.color : source.color };
  });
  const values = {
    custom_wood_color_doctype: config.wood_color_doctype,
    custom_color_sample_data: JSON.stringify({ part_list: partList, rows }),
  };
  if (!matching || !item.custom_wood_color_doctype) {
    values.custom_wood = config.wood_color || null;
    values.custom_metal = config.metal_color || null;
  } else if (item.custom_wood_color_doctype && item.custom_wood_color_doctype !== config.wood_color_doctype) {
    values.custom_wood = config.wood_color || null;
  }
  salesOrderColorInitializing.add(item);
  try { await frappe.model.set_value(cdt, cdn, values); }
  finally { salesOrderColorInitializing.delete(item); }
  renderSalesOrderColors(frm, cdt, cdn);
}

function renderSalesOrderColors(frm, cdt, cdn) {
  const item = locals[cdt]?.[cdn];
  const fields = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[cdn]?.grid_form?.fields_dict;
  if (!item || !fields) return;
  const partList = item.custom_part_list || item.part_list;
  const data = salesOrderStoredColors(item);
  const editable = frm.doc.docstatus === 0 && !frm.read_only;
  const esc = frappe.utils.escape_html;
  const views = [
    ['custom_part_list_color', __('Part List Color'), row => row.has_source_color],
    ['custom_color_sample_table', __('Color Sample Table'), row => Number(row.edite_color) === 1],
  ];
  for (const [field, label, include] of views) {
    const wrapper = fields[field]?.$wrapper;
    if (!wrapper) continue;
    wrapper.empty();
    if (!partList || data.part_list !== partList) continue;
    wrapper.append($('<h6>').text(label));
    const rows = data.rows.filter(include);
    if (!rows.length) {
      wrapper.append($('<p class="text-muted">').text(__('No matching materials.')));
      continue;
    }
    const table = $(`<table class="table table-bordered"><thead><tr><th>${__('Table')}</th><th>${__('Material')}</th><th>${__('Part Name')}</th><th>${__('Color')}</th></tr></thead><tbody></tbody></table>`).appendTo(wrapper);
    const labels = { panel_materials: __('Panel Materials'), metal_material: __('Metal Material'), other_material: __('Other Material') };
    for (const row of rows) {
      const tr = $(`<tr><td>${esc(labels[row.source_table] || '')}</td><td>${esc(row.material || '')}</td><td>${esc(row.part_name || '')}</td><td></td></tr>`).appendTo(table.find('tbody'));
      const control = frappe.ui.form.make_control({
        parent: tr.find('td').last(),
        df: {
          fieldname: 'color', fieldtype: 'Link', options: row.color_doctype,
          label: __('Color'), read_only: !editable || !row.color_doctype,
          onchange: async () => {
            if (!editable || (item.custom_part_list || item.part_list) !== partList) return;
            const current = salesOrderStoredColors(item);
            const selected = current.rows.find(candidate => candidate.source_row === row.source_row);
            if (current.part_list !== partList || !selected) return;
            selected.color = control.get_value() || null;
            await frappe.model.set_value(cdt, cdn, 'custom_color_sample_data', JSON.stringify(current));
            renderSalesOrderColors(frm, cdt, cdn);
          },
        },
        render_input: true,
      });
      control.set_input(row.color || '');
    }
  }
}

async function applySalesOrderHeaderColor(frm, cdt, cdn, table, field) {
  const item = locals[cdt]?.[cdn];
  if (!item || salesOrderColorInitializing.has(item)) return;
  const color = item[field] || null;
  let data = salesOrderStoredColors(item);
  const partList = item.custom_part_list || item.part_list;
  if (!partList) return;
  if (data.part_list !== partList) {
    await syncSalesOrderColors(frm, cdt, cdn);
    if ((item.custom_part_list || item.part_list) !== partList) return;
    data = salesOrderStoredColors(item);
    salesOrderColorInitializing.add(item);
    try { await frappe.model.set_value(cdt, cdn, field, color); }
    finally { salesOrderColorInitializing.delete(item); }
  }
  for (const row of data.rows) {
    if (row.source_table === table) row.color = color;
  }
  await frappe.model.set_value(cdt, cdn, 'custom_color_sample_data', JSON.stringify(data));
  renderSalesOrderColors(frm, cdt, cdn);
}

frappe.ui.form.on('Sales Order Item', {
  form_render: syncSalesOrderColors,
  custom_part_list: syncSalesOrderColors,
  part_list: syncSalesOrderColors,
  custom_wood(frm, cdt, cdn) {
    return applySalesOrderHeaderColor(frm, cdt, cdn, 'panel_materials', 'custom_wood');
  },
  custom_metal(frm, cdt, cdn) {
    return applySalesOrderHeaderColor(frm, cdt, cdn, 'metal_material', 'custom_metal');
  },
});
