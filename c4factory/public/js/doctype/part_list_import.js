/* Spreadsheet cells are data. Every displayed cell is escaped. */
(() => {
  const api = 'c4factory.api.part_list_import.';
  const tables = {
    panel_materials: 'Panel Materials', metal_material: 'Metal Material',
    other_material: 'Other Material', accessorise_table: 'Accessories',
  };
  const labels = {
    part_name: 'Part Name English', part_name_ar: 'Part Name Arabic', material: 'Material',
    lenght: 'Length', width: 'Width', hight: 'Height', thickness: 'Thickness', qty: 'Qty',
    note: 'Notes', requested_name: 'Requested Item Name',
  };
  const esc = value => frappe.utils.escape_html(String(value ?? ''));
  const column = index => {
    let result = '';
    for (let n = index + 1; n; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + (n - 1) % 26) + result;
    return result;
  };
  function parsePaste(text) {
    // Excel quotes cells containing tabs, newlines or quotes.
    const rows = []; let row = [], cell = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (char === '"' && (quoted || cell === '')) {
        if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
        else quoted = !quoted;
      } else if (!quoted && (char === '\t' || char === '\n' || char === '\r')) {
        row.push(cell); cell = '';
        if (char !== '\t') {
          if (char === '\r' && text[i + 1] === '\n') i++;
          rows.push(row); row = [];
        }
      } else cell += char;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    if (quoted) throw new Error(__('An Excel cell has an unclosed quote. Copy the range again.'));
    return rows;
  }

  function openImport(frm, table) {
    let workbook = null, matrix = [], source = 'paste', mappingDialog;
    const accessories = table === 'accessorise_table';
    const fields = accessories ? ['requested_name', 'qty', 'note'] :
      ['part_name', 'part_name_ar', 'lenght', 'width', 'hight', 'thickness', 'qty', 'material', 'note'];
    const dialog = new frappe.ui.Dialog({
      title: __('Import / Paste: {0}', [__(tables[table])]), size: 'extra-large',
      fields: [
        {fieldtype: 'HTML', options: `<p>${__('Paste a rectangular Excel range, including blank columns. Or upload a workbook and choose one sheet.')}</p>`},
        {fieldtype: 'Small Text', fieldname: 'paste', label: __('Excel cells'), description: __('Multiple rows and columns are supported. Names are stored as text.')},
        {fieldtype: 'Button', fieldname: 'upload', label: __('Upload Excel (.xls / .xlsx)')},
        {fieldtype: 'Button', fieldname: 'template', label: __('Download Template')},
        {fieldtype: 'Select', fieldname: 'sheet', label: __('Workbook Sheet'), hidden: 1},
      ],
      primary_action_label: __('Configure Columns'),
      primary_action: () => {
        try {
          if (source === 'paste') matrix = parsePaste(dialog.get_value('paste') || '');
          else matrix = workbook[dialog.get_value('sheet')] || [];
          if (!matrix.length) return frappe.msgprint(__('Paste cells or upload a workbook first.'));
          if (matrix.length > 3000 || matrix.some(r => r.length > 60)) return frappe.msgprint(__('Maximum 3,000 rows and 60 columns.'));
          configure();
        } catch (error) { frappe.msgprint(esc(error.message)); }
      },
    });
    dialog.fields_dict.paste.df.onchange = () => { source = 'paste'; };
    dialog.fields_dict.upload.df.click = () => new frappe.ui.FileUploader({
      restrictions: {allowed_file_types: ['.xls', '.xlsx'], max_file_size: 10 * 1024 * 1024},
      make_attachments_public: false, is_private: true, allow_toggle_private: false,
      on_success: async file => {
        const response = await frappe.call({method: api + 'inspect_workbook', args: {file_url: file.file_url}, freeze: true});
        workbook = response.message; source = 'workbook';
        const sheets = Object.keys(workbook);
        dialog.set_df_property('sheet', 'options', sheets.join('\n'));
        dialog.set_df_property('sheet', 'hidden', 0);
        await dialog.set_value('sheet', sheets.includes('Part L.') ? 'Part L.' : sheets[0]);
        frappe.show_alert(__('Workbook loaded. Choose one source sheet to avoid duplicates.'));
      },
    });
    dialog.fields_dict.template.df.click = () => window.open('/api/method/' + api + 'download_template?table=' + encodeURIComponent(table));
    dialog.show();

    function configure() {
      const count = Math.max(...matrix.map(r => r.length));
      const options = ['Skip', ...Array.from({length: count}, (_, i) => column(i))].join('\n');
      const sheetName = source === 'workbook' ? dialog.get_value('sheet') : 'paste';
      const signature = JSON.stringify(matrix.slice(0, 10).map(r => r.filter(v => typeof v === 'string').slice(0, 8)));
      const key = 'c4-part-import:' + table + ':' + sheetName + ':' + signature;
      let saved = {};
      try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (_) { /* fresh mapping */ }
      let start = 1, end = matrix.length;
      let defaults = Object.fromEntries(fields.map((f, i) => [f, i < count ? column(i) : 'Skip']));
      if (sheetName === 'Part L.') {
        defaults = accessories ? {requested_name: 'C', qty: 'K', note: 'G'} :
          {part_name: 'C', part_name_ar: 'D', lenght: 'G', width: 'H', hight: 'I', thickness: 'J', qty: 'K', material: 'Skip', note: 'Skip'};
        const marker = table === 'panel_materials' ? /^(wooden panel|panel)$/i : table === 'metal_material' ? /^metal$/i : table === 'accessorise_table' ? /^accessories$/i : /^other(s| material)?$/i;
        const section = matrix.findIndex(r => marker.test(String(r[0] || '').trim()));
        if (section >= 0) {
          start = section + (accessories ? 3 : 2);
          const next = matrix.findIndex((r, i) => i >= start - 1 && /^(metal|accessories|other(s| material)?|drawn by)$/i.test(String(r[0] || '').trim()));
          end = next >= 0 ? next : matrix.length;
        }
      } else {
        const header = matrix[0].map(v => String(v).trim().toLowerCase());
        const aliases = {part_name: ['part name english', 'bom lines/component/name'], part_name_ar: ['part name arabic'], requested_name: ['requested item name'], qty: ['qty', 'bom lines/quantity'], lenght: ['length', 'bom lines/length'], width: ['width', 'bom lines/width'], hight: ['height'], thickness: ['thickness', 'bom lines/thickness'], material: ['material'], note: ['notes']};
        if (fields.some(f => (aliases[f] || []).some(a => header.includes(a)))) {
          defaults = Object.fromEntries(fields.map(f => { const i = header.findIndex(h => (aliases[f] || []).includes(h)); return [f, i < 0 ? 'Skip' : column(i)]; }));
          start = 2;
        }
      }
      const sample = matrix.slice(0, 12).map((r, i) => `<tr><td>${i + 1}</td>${Array.from({length: count}, (_, c) => `<td>${esc(r[c])}</td>`).join('')}</tr>`).join('');
      mappingDialog = new frappe.ui.Dialog({
        title: __('Map Columns: {0}', [__(tables[table])]), size: 'extra-large',
        fields: [
          {fieldtype: 'HTML', options: `<div style="max-height:240px;overflow:auto"><table class="table table-bordered"><thead><tr><th>#</th>${Array.from({length: count}, (_, i) => `<th>${column(i)}</th>`).join('')}</tr></thead><tbody>${sample}</tbody></table></div><p>${__('Choose the data row range. Check Height and Thickness carefully; source headings can be incorrect.')}</p>`},
          {fieldtype: 'Int', fieldname: 'start', label: __('First Data Row'), default: start, reqd: 1},
          {fieldtype: 'Int', fieldname: 'end', label: __('Last Data Row'), default: end, reqd: 1},
          ...fields.map(f => ({fieldtype: 'Select', fieldname: f, label: __(labels[f]), options, default: saved[f] || defaults[f] || 'Skip'})),
          {fieldtype: 'Link', fieldname: 'default_material', label: __('Default Material for Imported Rows'), options: 'Part Material', hidden: accessories},
          {fieldtype: 'Select', fieldname: 'mode', label: __('Import Mode'), options: 'Add Rows\nReplace Table Rows', default: 'Add Rows'},
        ],
        primary_action_label: __('Preview Rows'),
        primary_action: async values => {
          const mapping = {};
          fields.forEach(f => { if (values[f] !== 'Skip') mapping[f] = Array.from({length: count}, (_, i) => column(i)).indexOf(values[f]); });
          const response = await frappe.call({method: api + 'preview_import', args: {
            matrix: JSON.stringify(matrix), mapping: JSON.stringify(mapping), table,
            material: values.default_material || '', start_row: values.start, end_row: values.end,
          }, freeze: true});
          try { localStorage.setItem(key, JSON.stringify(Object.fromEntries(fields.map(f => [f, values[f]])))); } catch (_) { /* storage is optional */ }
          preview(response.message, values.mode);
        },
      });
      mappingDialog.show();
    }

    function preview(rows, mode) {
      if (!rows.length) return frappe.msgprint(__('No data rows found.'));
      let adding = false;
      const content = rows.map((r, i) => {
        const assembly = /drawer unit/i.test(r.values.part_name || '');
        return `<tr><td><input type="checkbox" data-row="${i}" ${!r.errors.length && !assembly ? 'checked' : ''} ${r.errors.length ? 'disabled' : ''}></td><td>${r.source_row}</td>${fields.map(f => `<td>${esc(r.values[f])}</td>`).join('')}<td>${r.errors.map(esc).join('<br>')}${assembly ? esc(__('Possible assembly: select only if it should be counted alongside its components.')) : ''}</td></tr>`;
      }).join('');
      const p = new frappe.ui.Dialog({
        title: __('Review Import: {0}', [__(tables[table])]), size: 'extra-large',
        fields: [{fieldtype: 'HTML', fieldname: 'rows', options: `<p>${esc(mode)} — ${__('Only checked rows will be imported. Invalid rows must be corrected in the source or mapping.')}</p><div style="max-height:500px;overflow:auto"><table class="table table-bordered"><thead><tr><th>${__('Include')}</th><th>${__('Source Row')}</th>${fields.map(f => `<th>${__(labels[f])}</th>`).join('')}<th>${__('Review')}</th></tr></thead><tbody>${content}</tbody></table></div>`}],
        primary_action_label: __('Add Selected Rows'),
        primary_action: async () => {
          if (adding) return;
          if (frm.doc.docstatus !== 0 || frm.read_only) return frappe.msgprint(__('Import requires an editable draft.'));
          const selected = [...p.fields_dict.rows.$wrapper.find('input:checked')].map(el => rows[Number(el.dataset.row)]).filter(r => !r.errors.length);
          if (!selected.length) return frappe.msgprint(__('Select at least one valid row.'));
          adding = true;
          try {
            const palettes = {};
            const prepared = [];
            for (const entry of selected) {
              const values = {...entry.values};
              if (!accessories) {
                if (!(values.material in palettes)) {
                  const result = await frappe.db.get_value('Part Material', values.material, 'color_palette');
                  palettes[values.material] = result.message?.color_palette || null;
                }
                values.color_palette = palettes[values.material];
                values.color_doctype = values.color_palette ? 'Material Color' : null;
              } else values.mapping_status = 'Pending';
              prepared.push(values);
            }
            // Finish fallible lookups before changing any draft rows.
            if (frm.doc.docstatus !== 0 || frm.read_only) return frappe.msgprint(__('Import requires an editable draft.'));
            if (mode === 'Replace Table Rows') frm.clear_table(table);
            prepared.forEach(values => frm.add_child(table, values));
            frm.refresh_field(table); frm.dirty();
            p.hide(); mappingDialog.hide(); dialog.hide();
            frappe.show_alert(__('Added {0} rows. Save the Part List to validate and store them.', [selected.length]));
          } finally { adding = false; }
        },
      });
      p.show();
    }
  }

  function openMapping(frm) {
    const rows = frm.doc.accessorise_table || [];
    const fields = [];
    rows.forEach((row, i) => {
      fields.push({fieldtype: 'Section Break', label: esc(`${i + 1}. ${row.requested_name || row.item || ''} — ${row.qty}`)},
        {fieldtype: 'Link', fieldname: 'item_' + i, label: __('Stock Item'), options: 'Item', default: row.item, get_query: () => ({filters: {disabled: 0, is_stock_item: 1, has_variants: 0}})},
        {fieldtype: 'Link', fieldname: 'uom_' + i, label: __('Requested UOM'), options: 'UOM', default: row.requested_uom},
        {fieldtype: 'Float', fieldname: 'factor_' + i, label: __('Stock Units per Requested Unit'), default: row.conversion_factor || 1});
    });
    fields.unshift({fieldtype: 'HTML', options: `<p>${__('Confirm the requested unit for each selected Item. A blank UOM means its stock unit. Conversion must match the Item configuration.')}</p>`});
    const d = new frappe.ui.Dialog({title: __('Map Accessories'), size: 'large', fields,
      primary_action_label: __('Save Mappings'),
      primary_action: async values => {
        d.get_primary_btn().prop('disabled', true);
        try {
          await frappe.call({method: 'c4factory.api.part_list_accessories.map_accessories', args: {
            part_list: frm.doc.name, modified: frm.doc.modified,
            mappings: JSON.stringify(rows.map((r, i) => ({row: r.name, item: values['item_' + i], requested_uom: values['uom_' + i], conversion_factor: values['factor_' + i]}))),
          }, freeze: true});
          d.hide(); await frm.reload_doc();
        } finally { d.get_primary_btn().prop('disabled', false); }
      },
    });
    d.show();
  }
  frappe.ui.form.on('Part List', {
    refresh(frm) {
      if (frm.doc.docstatus === 0 && !frm.read_only) {
        Object.entries(tables).forEach(([table, label]) => frm.add_custom_button(__(label), () => openImport(frm, table), __('Import / Paste')));
      }
      const rows = frm.doc.accessorise_table || [];
      const matched = rows.filter(r => r.item).length;
      if (rows.length) frm.dashboard.add_indicator(__('Accessories mapped: {0} of {1}', [matched, rows.length]), matched === rows.length ? 'green' : 'orange');
      if (frm.doc.docstatus === 1 && rows.length && ['Stock User', 'Stock Manager', 'System Manager'].some(r => frappe.user_roles.includes(r))) {
        frm.add_custom_button(__('Map Accessories'), () => openMapping(frm));
      }
    },
  });
  if (typeof module !== 'undefined') module.exports = {parsePaste, column};
})();
