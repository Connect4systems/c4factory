// Both views edit the same per-item data; the original Part List is read-only.
const salesOrderColorRequests = new WeakMap();

function salesOrderColorGridForm(frm, cdn) {
  const row = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[cdn];
  if (row?.grid_form) return row.grid_form;
  if (frm.cur_grid?.doc?.name === cdn) return frm.cur_grid.grid_form;
  return null;
}

function salesOrderColorStatus(frm, cdn, message) {
  const fields = salesOrderColorGridForm(frm, cdn)?.fields_dict;
  for (const field of ['custom_part_list_color', 'custom_color_sample_table']) {
    fields?.[field]?.$wrapper.text(message);
  }
}

function salesOrderStoredColors(item) {
  try {
    const data = JSON.parse(item.custom_color_sample_data || '{}');
    return data && Array.isArray(data.rows) ? data : { rows: [] };
  } catch { return { rows: [] }; }
}

async function syncSalesOrderColors(frm, cdt, cdn, reset = false) {
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
    await frappe.model.set_value(cdt, cdn, { custom_color_sample_data: null });
    renderSalesOrderColors(frm, cdt, cdn);
    return;
  }
  salesOrderColorStatus(frm, cdn, __('Loading Part List colors...'));
  let result;
  try {
    result = await frappe.call({
      method: 'c4factory.api.sales_order_colors.get_part_list_colors',
      args: { part_list: partList },
    });
    if (!result.message || !Array.isArray(result.message.rows)) {
      throw new Error(__('The server did not return Part List color data.'));
    }
  } catch (error) {
    if (salesOrderColorRequests.get(item) === request) {
      salesOrderColorStatus(frm, cdn, __('Unable to load Part List colors. Click Update Part List to retry.'));
    }
    throw error;
  }
  if (salesOrderColorRequests.get(item) !== request || locals[cdt]?.[cdn] !== item ||
      (item.custom_part_list || item.part_list) !== partList) return;
  const config = result.message;
  const saved = salesOrderStoredColors(item);
  const matching = !reset && saved.part_list === partList;
  const choices = new Map((matching ? saved.rows : [])
    .filter(row => row && typeof row === 'object').map(row => [row.source_row, row]));
  const rows = (config.rows || []).map(source => {
    const choice = choices.get(source.source_row);
    return { ...source, color: !source.color_doctype ? null :
      choice?.color_doctype === source.color_doctype && choice?.color_palette === source.color_palette ? choice.color : source.color };
  });
  const values = {
    custom_color_sample_data: JSON.stringify({ part_list: partList, rows }),
  };
  // Python's JSON includes spaces. Formatting alone must not dirty a saved form
  // when an item is opened or its colors are refreshed.
  if (JSON.stringify(saved) === values.custom_color_sample_data) {
    delete values.custom_color_sample_data;
  }
  await frappe.model.set_value(cdt, cdn, values);
  renderSalesOrderColors(frm, cdt, cdn);
}

function renderSalesOrderColors(frm, cdt, cdn) {
  const item = locals[cdt]?.[cdn];
  const fields = salesOrderColorGridForm(frm, cdn)?.fields_dict;
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
    if (!partList) continue;
    wrapper.append($('<h6>').text(label));
    if (data.part_list !== partList) {
      wrapper.append($('<p class="text-muted">').text(__('Click Update Part List to load colors.')));
      continue;
    }
    const rows = data.rows.filter(include);
    if (!rows.length) {
      wrapper.append($('<p class="text-muted">').text(__('No matching materials.')));
      continue;
    }
    const table = $(`<table class="table table-bordered"><thead><tr><th>${__('Table')}</th><th>${__('Material')}</th><th>${__('Part Name')}</th><th>${__('Color')}</th></tr></thead><tbody></tbody></table>`).appendTo(wrapper);
    const labels = { panel_materials: __('Panel Materials'), metal_material: __('Metal Material'), other_material: __('Other Material') };
    for (const row of rows) {
      const tr = $(`<tr><td>${esc(labels[row.source_table] || '')}</td><td>${esc(row.material || '')}</td><td>${esc(row.part_name || '')}</td><td></td></tr>`).appendTo(table.find('tbody'));
      if (field === 'custom_part_list_color') {
        tr.find('td').last().text(row.color || '');
        continue;
      }
      const control = frappe.ui.form.make_control({
        parent: tr.find('td').last(),
        df: {
          fieldname: 'color', fieldtype: 'Link', options: row.color_doctype,
          label: __('Color'), read_only: !editable || !row.color_palette,
          get_query: () => ({filters: {palette: row.color_palette || ''}}),
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

for (const colorItemType of ['Sales Order Item', 'Color Sample Item']) {
  frappe.ui.form.on(colorItemType, {
    async custom_update_part_list(frm, cdt, cdn) {
      await syncSalesOrderColors(frm, cdt, cdn, true);
      frappe.show_alert({ message: __('Part List colors updated for this item.'), indicator: 'green' });
    },
    form_render: syncSalesOrderColors,
    custom_part_list: syncSalesOrderColors,
    part_list: syncSalesOrderColors,
  });
}
