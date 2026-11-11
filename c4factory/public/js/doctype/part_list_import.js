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
  const materialColumns = ['part_name', 'part_name_ar', 'lenght', 'width', 'hight', 'thickness', 'qty', 'material', 'note', 'edite_color', 'basic_color'];
  function prepareCellPaste(text, fieldname) {
    const start = materialColumns.indexOf(fieldname);
    if (start < 0) throw new Error(__('Choose a material table cell first.'));
    const matrix = parsePaste(text);
    if (matrix.length > 3000 || matrix.some(row => row.length + start > materialColumns.length)) {
      throw new Error(__('Paste up to 3,000 rows and keep columns within the table.'));
    }
    return matrix.map(row => Object.fromEntries(row.map((value, index) => {
      const field = materialColumns[start + index];
      if (['lenght', 'width', 'hight', 'thickness', 'qty'].includes(field)) {
        const number = value.trim() === '' ? 0 : Number(value);
        if (!Number.isFinite(number)) throw new Error(__('Invalid number in {0}: {1}', [field, value]));
        return [field, number];
      }
      if (field === 'edite_color') {
        const check = value.trim().toLowerCase();
        if (!['', '0', '1', 'true', 'false', 'yes', 'no'].includes(check)) throw new Error(__('Edite Color accepts 1/0, Yes/No, or True/False.'));
        return [field, ['1', 'true', 'yes'].includes(check) ? 1 : 0];
      }
      return [field, value];
    })));
  }

  async function pasteIntoCells(frm, table, rowIndex, fieldname, text) {
    const values = prepareCellPaste(text, fieldname);
    if (frm.doc.docstatus !== 0 || frm.read_only || frm._partCellPaste) return;
    frm._partCellPaste = true;
    try {
      for (let index = 0; index < values.length; index++) {
        const row = frm.doc[table]?.[rowIndex + index] || frm.add_child(table);
        // Run normal change handlers, including material/palette dependencies,
        // before applying a pasted Color later in the same row.
        for (const [field, value] of Object.entries(values[index])) {
          await frappe.model.set_value(row.doctype, row.name, field, value);
        }
      }
      frm.dirty();
    } finally {
      frm._partCellPaste = false;
      frm.refresh_field(table);
    }
  }
  const column = index => {
    let result = '';
    for (let n = index + 1; n; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + (n - 1) % 26) + result;
    return result;
  };
  function populatedColumns(matrix) {
    const count = Math.max(0, ...matrix.map(row => row.length));
    return Array.from({length: count}, (_, index) => index)
      .filter(index => matrix.some(row => String(row[index] ?? '').trim() !== ''));
  }
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

  function sectionType(label) {
    const text = String(label || '').trim().toLowerCase().replace(/[._-]+/g, ' ').replace(/\s+/g, ' ');
    if (/^(wood(en|in)? panels?|panels?|panel materials?|materials?|wood|خشب|الخشب|ألواح خشبية)$/.test(text)) return 'panel_materials';
    if (/^(metal(s| materials?)?|steel|معدن|المعدن|معادن)$/.test(text)) return 'metal_material';
    if (/^(other(s| materials?)?|أخرى|اخرى)$/.test(text)) return 'other_material';
    if (/^(accessor(y|ies|ise)( materials?)?|اكسسوارات|إكسسوارات)$/.test(text)) return 'accessorise_table';
    return null;
  }

  function detectSections(matrix) {
    const sections = [];
    matrix.forEach((row, index) => {
      const cells = row.slice(0, 11);
      const first = cells.find(v => String(v ?? '').trim());
      if (typeof first !== 'string') return;
      if (cells.some(v => String(v ?? '').trim() && Number.isFinite(Number(v)))) return;
      if (cells.filter(v => /^(sn|code|materials?|qty\.?|u\.?o\.?m\.?|dim\.?)$/i.test(String(v || '').trim())).length >= 2) return;
      const table = sectionType(first);
      if (table) sections.push({index, label: first.trim(), table});
    });
    return sections;
  }

  function sectionRange(matrix, section, sections) {
    let start = section.index + 2;
    const next = sections.find(s => s.index > section.index);
    let end = next ? next.index : matrix.length;
    const footer = matrix.findIndex((r, i) => i > section.index && /^(drawn by|draw by|checked by|revision no\.?)$/i.test(String(r.find(v => String(v ?? '').trim()) || '').trim()));
    if (footer >= 0) end = Math.min(end, footer);
    // Accessories commonly have a second header row: Code / Items / Supplier / Qty.
    while (start <= end) {
      const cells = matrix[start - 1].map(v => String(v ?? '').trim().toLowerCase()).filter(Boolean);
      const header = cells.filter(v => /^(sn|s n|code|items?|materials?|qty\.?|quantity|supplier|notes|u\.?o\.?m\.?)$/.test(v)).length >= 2;
      if (cells.length && !header) break;
      start++;
    }
    return {start, end};
  }

  function openImport(frm, table, pastedText = '') {
    const importAll = table === 'all';
    let workbook = null, matrix = [], source = 'paste', mappingDialog, sectionDialog;
    let workbookLoading = null;
    const loadWorkbook = async fileUrl => {
      const response = await frappe.call({method: api + 'inspect_workbook', args: {file_url: fileUrl}, freeze: true});
      workbook = response.message; source = 'workbook';
      const sheets = Object.keys(workbook);
      dialog.set_df_property('sheet', 'options', sheets.join('\n'));
      dialog.set_df_property('sheet', 'hidden', 0);
      await dialog.set_value('sheet', sheets.includes('Part L.') ? 'Part L.' : sheets[0]);
    };
    const dialog = new frappe.ui.Dialog({
      title: __('Import / Paste: {0}', [__(importAll ? 'All Tables' : tables[table])]), size: 'extra-large',
      fields: [
        {fieldtype: 'HTML', options: `<p>${__('Paste a rectangular Excel range, including blank columns. Or upload a workbook and choose one sheet.')}</p>`},
        {fieldtype: 'Small Text', fieldname: 'paste', label: __('Excel cells'), description: __('Multiple rows and columns are supported. Names are stored as text.')},
        {fieldtype: 'Button', fieldname: 'upload', label: __('Upload Excel (.xls / .xlsx)')},
        {fieldtype: 'Button', fieldname: 'template', label: __('Download Template')},
        {fieldtype: 'Select', fieldname: 'sheet', label: __('Workbook Sheet'), hidden: 1},
      ],
      primary_action_label: __('Configure Columns'),
      primary_action: async () => {
        try {
          if (workbookLoading) await workbookLoading;
          if (source === 'paste') matrix = parsePaste(dialog.get_value('paste') || '');
          else matrix = workbook[dialog.get_value('sheet')] || [];
          if (!matrix.length) return frappe.msgprint(__('Paste cells or upload a workbook first.'));
          if (matrix.length > 3000 || matrix.some(r => r.length > 60)) return frappe.msgprint(__('Maximum 3,000 rows and 60 columns.'));
          if (importAll) configureAll();
          else chooseSection();
        } catch (error) { frappe.msgprint(esc(error.message)); }
      },
    });
    dialog.fields_dict.paste.df.onchange = () => { source = 'paste'; };
    dialog.fields_dict.upload.df.click = () => new frappe.ui.FileUploader({
      restrictions: {allowed_file_types: ['.xls', '.xlsx'], max_file_size: 10 * 1024 * 1024},
      make_attachments_public: false, is_private: true, allow_toggle_private: false,
      doctype: frm.doc.doctype || 'Part List', docname: frm.doc.name, fieldname: 'pds_table',
      on_success: async file => {
        await loadWorkbook(file.file_url);
        const existing = (frm.doc.pds_table || []).find(row => row.title === 'Part File');
        if (existing) existing.arttach = file.file_url;
        else frm.add_child('pds_table', {title: 'Part File', arttach: file.file_url});
        frm.refresh_field('pds_table'); frm.dirty();
        frappe.show_alert(__('Workbook linked in PDS Table as Part File. Save the Part List to keep it for future imports.'));
      },
    });
    dialog.fields_dict.template.df.click = () => window.open('/api/method/' + api + 'download_template?table=' + encodeURIComponent(table));
    dialog.show();
    if (pastedText) dialog.set_value('paste', pastedText);
    else if (getPartWorkbook(frm.doc)) {
      workbookLoading = loadWorkbook(getPartWorkbook(frm.doc)).catch(error => {
        frappe.msgprint(esc(error.message));
      }).finally(() => { workbookLoading = null; });
    }

    function configureAll() {
      const sections = detectSections(matrix);
      // A plain sheet can still be imported by confirming its destination and range.
      const sources = sections.length ? sections : [{index: -1, label: __('Whole sheet / pasted rows'), table: 'panel_materials'}];
      const count = Math.max(...matrix.map(row => row.length));
      const columns = populatedColumns(matrix).map(column);
      const columnOptions = ['Skip', ...columns].join('\n');
      const materialFields = ['part_name', 'part_name_ar', 'lenght', 'width', 'hight', 'thickness', 'qty', 'material', 'note'];
      const aliases = {
        part_name: ['part name english', 'part name', 'bom lines/component/name'], part_name_ar: ['part name arabic'],
        requested_name: ['requested item name', 'items', 'item'], qty: ['qty', 'qty.', 'quantity', 'bom lines/quantity'],
        lenght: ['length', 'bom lines/length'], width: ['width', 'bom lines/width'], hight: ['height'],
        thickness: ['thickness', 'bom lines/thickness'], material: ['material'], note: ['notes', 'note'],
      };
      const configs = sources.map(section => {
        const range = section.index < 0 ? {start: 1, end: matrix.length} : sectionRange(matrix, section, sections);
        const headerIndex = section.index < 0 ? 0 : Math.max(section.index + 1, range.start - 2);
        const headers = matrix[headerIndex] || [];
        const normalized = headers.map(value => String(value ?? '').trim().toLowerCase());
        const recognized = Object.values(aliases).some(names => names.some(name => normalized.includes(name)));
        if (section.index < 0 && recognized) range.start = 2;
        const legacy = count >= 11 && section.index >= 0;
        const fallback = legacy ? {part_name: 'C', part_name_ar: 'D', lenght: 'G', width: 'H', hight: 'I', thickness: 'J', qty: 'K', requested_name: 'C', note: section.table === 'accessorise_table' ? 'G' : 'Skip'} : {};
        const defaults = Object.fromEntries([...materialFields, 'requested_name'].map(field => {
          const index = normalized.findIndex(header => (aliases[field] || []).includes(header));
          return [field, index >= 0 ? column(index) : fallback[field] || 'Skip'];
        }));
        return {section, range, headers, defaults};
      });
      const choices = sources.map(section => section.index < 0 ? section.label : `${section.index + 1}: ${section.label}`);
      const slots = Object.keys(tables).map(table => ({table, source: sources.findIndex(section => section.table === table)}));
      const common = configs.find(config => config.section.table !== 'accessorise_table') || configs[0];
      const defaults = {...common.defaults};
      if (defaults.part_name === 'Skip') defaults.part_name = common.defaults.requested_name;
      let setup;
      const fields = [
        {fieldtype: 'HTML', options: `<p>${__('Confirm the four section rows below. Select an Excel header, its system table, and a Part Material where needed. Column mapping is shared by all selected sections, including accessories.')}</p>`},
        {fieldtype: 'Select', fieldname: 'mode', label: __('Import Mode'), options: 'Add Rows\nReplace Table Rows', default: 'Add Rows'},
        {fieldtype: 'Section Break', label: __('Excel Sections and System Tables')},
        ...slots.map((slot, i) => ({fieldtype: 'Select', fieldname: `section_${i}_header`, label: __('Excel Header'),
          options: ['Skip', ...choices].join('\n'), default: slot.source < 0 ? 'Skip' : choices[slot.source]})),
        {fieldtype: 'Column Break'},
        ...slots.map((slot, i) => ({fieldtype: 'Select', fieldname: `section_${i}_table`, label: __('System Table'),
          options: ['Skip', ...Object.values(tables)].join('\n'), default: tables[slot.table],
          onchange: () => {
            if (!setup) return;
            const target = setup.get_value(`section_${i}_table`);
            setup.set_df_property(`section_${i}_default_material`, 'hidden', target === tables.accessorise_table || target === 'Skip');
          }})),
        {fieldtype: 'Column Break'},
        ...slots.map((slot, i) => ({fieldtype: 'Link', fieldname: `section_${i}_default_material`, label: __('Part Material'),
          options: 'Part Material', hidden: slot.table === 'accessorise_table'})),
        {fieldtype: 'Section Break', label: __('Shared Column Mapping')},
        {fieldtype: 'HTML', options: `<p>${__('Map columns once for all tables. The name column also supplies Requested Item Name for accessories. Data ranges are detected from the selected section headers.')}</p><div style="overflow:auto;max-height:240px"><table class="table table-bordered"><thead><tr><th>#</th>${columns.map(col => `<th>${col}</th>`).join('')}</tr></thead><tbody>${matrix.slice(0, 12).map((row, i) => `<tr><td>${i + 1}</td>${columns.map((_, c) => `<td>${esc(row[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`},
        ...materialFields.map(field => ({fieldtype: 'Select', fieldname: 'map_' + field,
          label: field === 'part_name' ? __('Part Name English / Requested Item Name') : __(labels[field]),
          options: columnOptions, default: columns.includes(defaults[field]) ? defaults[field] : 'Skip'})),
      ];
      setup = new frappe.ui.Dialog({title: __('Import All: Confirm Headers and Columns'), size: 'extra-large', fields,
        primary_action_label: __('Preview All Tables'),
        primary_action: async values => {
          setup.get_primary_btn().prop('disabled', true);
          try {
            const batches = [];
            const selectedSections = new Set();
            for (let i = 0; i < slots.length; i++) {
              const prefix = `section_${i}_`;
              const target = values[prefix + 'table'];
              const choice = values[prefix + 'header'];
              if (target === 'Skip' || choice === 'Skip') continue;
              if (selectedSections.has(choice)) return frappe.msgprint(__('Select each Excel header only once.'));
              selectedSections.add(choice);
              const config = configs[choices.indexOf(choice)];
              if (!config) return frappe.msgprint(__('Choose an Excel header for each included row.'));
              const table = Object.keys(tables).find(key => tables[key] === target);
              const mappedFields = table === 'accessorise_table' ? ['requested_name', 'qty', 'note'] : materialFields;
              const mapping = {};
              mappedFields.forEach(field => {
                const index = columns.indexOf(values['map_' + (field === 'requested_name' ? 'part_name' : field)]);
                if (index >= 0) mapping[field] = index;
              });
              if (table !== 'accessorise_table' && !values[prefix + 'default_material'] && mapping.material === undefined) {
                return frappe.msgprint(__('Choose a Part Material or map the Material column for {0}.', [esc(config.section.label)]));
              }
              if (config.range.start > config.range.end) continue;
              const response = await frappe.call({method: api + 'preview_import', args: {
                matrix: JSON.stringify(matrix), mapping: JSON.stringify(mapping), table,
                material: values[prefix + 'default_material'] || '', start_row: config.range.start, end_row: config.range.end,
              }, freeze: true});
              batches.push({table, label: config.section.label, rows: response.message});
            }
            if (!batches.some(batch => batch.rows.length)) return frappe.msgprint(__('No data rows found.'));
            const entries = batches.flatMap(batch => batch.rows.map(row => ({...row, table: batch.table, section: batch.label})));
            let importing = false;
            const review = new frappe.ui.Dialog({title: __('Review Import: All Tables'), size: 'extra-large', fields: [
              {fieldtype: 'HTML', options: `<p>${esc(values.mode)}. ${__('Rows with errors are disabled. Return to mapping to correct them. Possible assembly rows start unchecked.')}</p>`},
              {fieldtype: 'Button', fieldname: 'back', label: __('Back to Mapping'), click: () => {review.hide(); setup.show();}},
              {fieldtype: 'HTML', fieldname: 'rows', options: `<div style="max-height:500px;overflow:auto"><table class="table table-bordered"><thead><tr><th>${__('Include')}</th><th>${__('Excel Section')}</th><th>${__('Table')}</th><th>${__('Source Row')}</th><th>${__('Name')}</th><th>${__('Material')}</th><th>${__('Qty')}</th><th>${__('Review')}</th></tr></thead><tbody>${entries.map((row, i) => `<tr${/drawer unit/i.test(row.values.part_name || '') ? ' class="table-warning"' : ''}><td><input type="checkbox" data-row="${i}" ${row.errors.length ? 'disabled' : /drawer unit/i.test(row.values.part_name || '') ? '' : 'checked'}></td><td>${esc(row.section)}</td><td>${esc(tables[row.table])}</td><td>${row.source_row}</td><td>${esc(row.values.part_name || row.values.requested_name)}</td><td>${esc(row.values.material)}</td><td>${esc(row.values.qty)}</td><td>${row.errors.map(esc).join('<br>')}${/drawer unit/i.test(row.values.part_name || '') ? '<div class="font-weight-bold">' + esc(__('Possible assembly: select only if it should be counted alongside its components.')) + '</div>' : ''}</td></tr>`).join('')}</tbody></table></div>`},
            ], primary_action_label: __('Import All Selected Rows'), primary_action: async () => {
              if (importing) return;
              const selected = [...review.fields_dict.rows.$wrapper.find('input:checked')].map(input => entries[Number(input.dataset.row)]).filter(row => !row.errors.length);
              if (!selected.length) return frappe.msgprint(__('Select at least one valid row.'));
              importing = true;
              review.get_primary_btn().prop('disabled', true);
              try {
                await applyImportBatches(frm, Object.keys(tables).map(table => ({table, rows: selected.filter(row => row.table === table)})).filter(batch => batch.rows.length), values.mode);
                review.hide(); setup.hide(); dialog.hide();
                frappe.show_alert(__('Added {0} rows. Save the Part List to validate and store them.', [selected.length]));
              } finally {importing = false; review.get_primary_btn().prop('disabled', false);}
            }});
            review.show();
          } finally {setup.get_primary_btn().prop('disabled', false);}
        },
      });
      setup.show();
    }

    function chooseSection() {
      const sections = detectSections(matrix);
      if (!sections.length) return configure();
      const choices = sections.map(s => `${s.index + 1}: ${s.label}`);
      const initial = sections.find(s => s.table === table) || sections[0];
      const selected = () => sections[choices.indexOf(sectionDialog.get_value('source_section'))];
      sectionDialog = new frappe.ui.Dialog({
        title: __('Map Excel Section'), size: 'large',
        fields: [
          {fieldtype: 'HTML', options: `<p>${__('Choose an Excel section header, then the table and material for its rows. The range ends at the next section header.')}</p>`},
          {fieldtype: 'Select', fieldname: 'source_section', label: __('Excel Section Header'), options: ['Whole sheet / pasted rows', ...choices].join('\n'), default: `${initial.index + 1}: ${initial.label}`,
            onchange: async () => {
              if (!sectionDialog) return;
              const section = selected();
              if (section) await sectionDialog.set_value('target_table', tables[section.table]);
            }},
          {fieldtype: 'Select', fieldname: 'target_table', label: __('Import into Table'), options: Object.values(tables).join('\n'), default: tables[initial.table], reqd: 1,
            onchange: () => {
              if (sectionDialog) sectionDialog.set_df_property('section_material', 'hidden', sectionDialog.get_value('target_table') === tables.accessorise_table);
            }},
          {fieldtype: 'Link', fieldname: 'section_material', label: __('Part Material for this Section'), options: 'Part Material', hidden: initial.table === 'accessorise_table', description: __('Applied to the imported rows. You can also map a Material column in the next step.')},
        ],
        primary_action_label: __('Map Columns'),
        primary_action: values => {
          table = Object.keys(tables).find(key => tables[key] === values.target_table);
          const section = selected();
          configure(section, sections, values.section_material || '');
        },
      });
      sectionDialog.show();
    }

    function configure(section = null, sections = [], sectionMaterial = '', targetTable = table) {
      const table = targetTable;
      const accessories = table === 'accessorise_table';
      const fields = accessories ? ['requested_name', 'qty', 'note'] :
        ['part_name', 'part_name_ar', 'lenght', 'width', 'hight', 'thickness', 'qty', 'material', 'note'];
      const count = Math.max(...matrix.map(r => r.length));
      const columns = populatedColumns(matrix).map(column);
      const options = ['Skip', ...columns].join('\n');
      const sheetName = source === 'workbook' ? dialog.get_value('sheet') : 'paste';
      const signature = JSON.stringify(matrix.slice(0, 10).map(r => r.filter(v => typeof v === 'string').slice(0, 8)));
      const key = 'c4-part-import:' + table + ':' + sheetName + ':' + signature;
      let saved = {};
      try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (_) { /* fresh mapping */ }
      let start = 1, end = matrix.length;
      let defaults = Object.fromEntries(fields.map((f, i) => [f, i < count ? column(i) : 'Skip']));
      if (!accessories && count === 9 && matrix.every(r => !String(r[2] ?? '').trim() && !String(r[3] ?? '').trim())) {
        // The customer's C:K range includes the two blank columns E and F.
        defaults = {part_name: 'A', part_name_ar: 'B', lenght: 'E', width: 'F', hight: 'G', thickness: 'H', qty: 'I', material: 'Skip', note: 'Skip'};
      } else if (sheetName === 'Part L.' || (section && count >= 11)) {
        defaults = accessories ? {requested_name: 'C', qty: 'K', note: 'G'} :
          {part_name: 'C', part_name_ar: 'D', lenght: 'G', width: 'H', hight: 'I', thickness: 'J', qty: 'K', material: 'Skip', note: 'Skip'};
      } else {
        const header = matrix[0].map(v => String(v).trim().toLowerCase());
        const aliases = {part_name: ['part name english', 'bom lines/component/name'], part_name_ar: ['part name arabic'], requested_name: ['requested item name'], qty: ['qty', 'bom lines/quantity'], lenght: ['length', 'bom lines/length'], width: ['width', 'bom lines/width'], hight: ['height'], thickness: ['thickness', 'bom lines/thickness'], material: ['material'], note: ['notes']};
        if (fields.some(f => (aliases[f] || []).some(a => header.includes(a)))) {
          defaults = Object.fromEntries(fields.map(f => { const i = header.findIndex(h => (aliases[f] || []).includes(h)); return [f, i < 0 ? 'Skip' : column(i)]; }));
          start = 2;
        }
      }
      if (section) ({start, end} = sectionRange(matrix, section, sections));
      if (start > end) return frappe.msgprint(__('The selected section has no data rows. Choose another section.'));
      const sampleStart = section ? section.index : 0;
      const sample = matrix.slice(sampleStart, sampleStart + 12).map((r, i) => `<tr><td>${sampleStart + i + 1}</td>${Array.from({length: count}, (_, c) => `<td>${esc(r[c])}</td>`).join('')}</tr>`).join('');
      mappingDialog = new frappe.ui.Dialog({
        title: __('Map Columns: {0}', [__(tables[table])]), size: 'extra-large',
        fields: [
          {fieldtype: 'HTML', options: `<div style="max-height:240px;overflow:auto"><table class="table table-bordered"><thead><tr><th>#</th>${Array.from({length: count}, (_, i) => `<th>${column(i)}</th>`).join('')}</tr></thead><tbody>${sample}</tbody></table></div><p>${__('Choose the data row range. Check Height and Thickness carefully; source headings can be incorrect.')}</p>`},
          {fieldtype: 'Int', fieldname: 'start', label: __('First Data Row'), default: start, reqd: 1},
          {fieldtype: 'Int', fieldname: 'end', label: __('Last Data Row'), default: end, reqd: 1},
          {fieldtype: 'Link', fieldname: 'default_material', label: __('Part Material for Imported Rows'), options: 'Part Material', hidden: accessories, default: sectionMaterial,
            description: __('Select a Part Material here, or map the Material column below. This is required before reviewing rows.')},
          {fieldtype: 'Section Break', label: __('Column Mapping')},
          ...fields.map(f => {
            const selected = saved[f] || defaults[f];
            return {fieldtype: 'Select', fieldname: f, label: __(labels[f]), options,
              default: columns.includes(selected) ? selected : 'Skip'};
          }),
          {fieldtype: 'Select', fieldname: 'mode', label: __('Import Mode'), options: 'Add Rows\nReplace Table Rows', default: 'Add Rows'},
        ],
        primary_action_label: __('Preview Rows'),
        primary_action: async values => {
          if (!accessories && !values.default_material && values.material === 'Skip') {
            frappe.msgprint(__('Choose a Part Material for this section, or map an Excel Material column, before reviewing rows.'));
            return;
          }
          const mapping = {};
          fields.forEach(f => { if (values[f] !== 'Skip') mapping[f] = Array.from({length: count}, (_, i) => column(i)).indexOf(values[f]); });
          const response = await frappe.call({method: api + 'preview_import', args: {
            matrix: JSON.stringify(matrix), mapping: JSON.stringify(mapping), table,
            material: values.default_material || '', start_row: values.start, end_row: values.end,
          }, freeze: true});
          try { localStorage.setItem(key, JSON.stringify(Object.fromEntries(fields.map(f => [f, values[f]])))); } catch (_) { /* storage is optional */ }
          const refreshMaterial = async material => {
            await mappingDialog.set_value('default_material', material);
            const refreshed = await frappe.call({method: api + 'preview_import', args: {
              matrix: JSON.stringify(matrix), mapping: JSON.stringify(mapping), table,
              material, start_row: values.start, end_row: values.end,
            }, freeze: true});
            return refreshed.message;
          };
          preview(response.message, values.mode, fields, accessories, table, refreshMaterial, values.default_material || '');
        },
      });
      mappingDialog.show();
    }

    function preview(rows, mode, fields, accessories, table, refreshMaterial, material = '') {
      if (!rows.length) return frappe.msgprint(__('No data rows found.'));
      let adding = false;
      const content = rows.map((r, i) => {
        const assembly = /drawer unit/i.test(r.values.part_name || '');
        return `<tr${assembly ? ' class="table-warning"' : ''}><td><input type="checkbox" data-row="${i}" ${!r.errors.length && !assembly ? 'checked' : ''} ${r.errors.length ? 'disabled' : ''}></td><td>${r.source_row}</td>${fields.map(f => `<td>${esc(r.values[f])}</td>`).join('')}<td>${r.errors.map(esc).join('<br>')}${assembly ? '<div class="font-weight-bold">' + esc(__('Possible assembly: select only if it should be counted alongside its components.')) + '</div>' : ''}</td></tr>`;
      }).join('');
      const p = new frappe.ui.Dialog({
        title: __('Review Import: {0}', [__(tables[table])]), size: 'extra-large',
        fields: [
          ...(!accessories && rows.some(r => !r.values.material) ? [
            {fieldtype: 'Link', fieldname: 'review_material', label: __('Part Material for Rows Missing a Material'), options: 'Part Material',
              default: material,
              description: __('Choose a material and apply it to enable rows with a missing material.')},
            {fieldtype: 'Button', fieldname: 'apply_material', label: __('Apply Material'), click: async () => {
              const material = p.get_value('review_material');
              if (!material) return frappe.msgprint(__('Select a material first.'));
              if (adding) return;
              adding = true;
              try {
                const refreshed = await refreshMaterial(material);
                p.hide();
                preview(refreshed, mode, fields, accessories, table, refreshMaterial, material);
              } finally { adding = false; }
            }},
          ] : []),
          {fieldtype: 'Button', fieldname: 'select_all', label: __('Select All Valid Rows'), click: () => {
            for (const input of p.fields_dict.rows.$wrapper.find('input:not(:disabled)')) input.checked = true;
          }},
          {fieldtype: 'Button', fieldname: 'deselect_all', label: __('Deselect All'), click: () => {
            for (const input of p.fields_dict.rows.$wrapper.find('input')) input.checked = false;
          }},
          {fieldtype: 'Button', fieldname: 'back_to_mapping', label: __('Back to Mapping'), click: () => {p.hide(); mappingDialog.show();}},
          {fieldtype: 'HTML', fieldname: 'rows', options: `<p>${esc(mode)} — ${__('Click a row or its checkbox to include it. Rows with errors are disabled; use Back to Mapping to correct them.')}</p><div style="max-height:500px;overflow:auto"><table class="table table-bordered"><thead><tr><th>${__('Include')}</th><th>${__('Source Row')}</th>${fields.map(f => `<th>${__(labels[f])}</th>`).join('')}<th>${__('Review')}</th></tr></thead><tbody>${content}</tbody></table></div>`},
        ],
        primary_action_label: __('Add Selected Rows'),
        primary_action: async () => {
          if (adding) return;
          if (frm.doc.docstatus !== 0 || frm.read_only) return frappe.msgprint(__('Import requires an editable draft.'));
          const selected = [...p.fields_dict.rows.$wrapper.find('input:checked')].map(el => rows[Number(el.dataset.row)]).filter(r => !r.errors.length);
          if (!selected.length) return frappe.msgprint(__('Select at least one valid row.'));
          adding = true;
          try {
            await applyImportBatches(frm, [{table, rows: selected}], mode);
            p.hide(); mappingDialog.hide(); sectionDialog?.hide(); dialog.hide();
            frappe.show_alert(__('Added {0} rows. Save the Part List to validate and store them.', [selected.length]));
          } finally { adding = false; }
        },
      });
      p.show();
      for (const tr of p.fields_dict.rows.$wrapper.find('tbody tr')) {
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', event => {
          if (event.target.closest('input, button, a, select')) return;
          const input = tr.querySelector('input');
          if (input && !input.disabled) input.checked = !input.checked;
        });
      }
    }
  }

  async function applyImportBatches(frm, batches, mode) {
    const assertEditable = () => {
      if (frm.doc.docstatus !== 0 || frm.read_only) throw new Error(__('Import requires an editable draft.'));
    };
    assertEditable();
    const palettes = {};
    const prepared = [];
    // Resolve every material before changing any of the destination tables.
    for (const batch of batches) {
      const rows = [];
      for (const entry of batch.rows) {
        const values = {...entry.values};
        if (batch.table === 'accessorise_table') values.mapping_status = 'Pending';
        else {
          if (!(values.material in palettes)) {
            const result = await frappe.db.get_value('Part Material', values.material, 'color_palette');
            palettes[values.material] = result.message?.color_palette || null;
          }
          values.color_palette = palettes[values.material];
          values.color_doctype = values.color_palette ? 'Material Color' : null;
        }
        rows.push(values);
      }
      prepared.push({table: batch.table, rows});
    }
    assertEditable();
    for (const {table, rows} of prepared) {
      if (mode === 'Replace Table Rows') frm.clear_table(table);
      else {
        const empty = (frm.doc[table] || []).filter(isEmptyImportRow);
        empty.forEach(row => {
          if (row.doctype && row.name) frappe.model.clear_doc(row.doctype, row.name);
        });
        frm.doc[table] = (frm.doc[table] || []).filter(row => !empty.includes(row));
        frm.doc[table].forEach((row, index) => {row.idx = index + 1;});
      }
      rows.forEach(values => frm.add_child(table, values));
      frm.refresh_field(table);
    }
    frm.dirty();
  }

  function isEmptyImportRow(row) {
    const text = ['material', 'part_name', 'part_name_ar', 'note', 'requested_name', 'item', 'basic_color', 'color_palette', 'color_doctype', 'requested_uom', 'stock_uom'];
    const numbers = ['qty', 'lenght', 'width', 'hight', 'thickness', 'edite_color', 'stock_qty', 'conversion_factor'];
    return text.every(key => !String(row[key] ?? '').trim()) && numbers.every(key => !Number(row[key] || 0));
  }

  function getPartWorkbook(doc) {
    const rows = (doc.pds_table || []).filter(row => /\.xlsx?(?:[?#]|$)/i.test(row.arttach || ''));
    return (rows.find(row => row.title === 'Part File') || rows[0])?.arttach || '';
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
        frm.add_custom_button(__('All Tables'), () => openImport(frm, 'all'), __('Import / Paste'));
        Object.entries(tables).forEach(([table, label]) => frm.add_custom_button(__(label), () => openImport(frm, table), __('Import / Paste')));
        Object.keys(tables).forEach(table => {
          const wrapper = frm.fields_dict?.[table]?.grid?.wrapper?.[0];
          if (!wrapper || wrapper._partImportPaste) return;
          wrapper._partImportPaste = true;
          wrapper.addEventListener('paste', event => {
            if (frm.doc.docstatus !== 0 || frm.read_only) return;
            const text = event.clipboardData?.getData('text/plain') || '';
            if (!/[\t\r\n]/.test(text)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            const grid = frm.fields_dict[table].grid;
            const cell = event.target.closest?.('[data-fieldname]');
            const rowElement = event.target.closest?.('.grid-row[data-name]');
            const gridRow = grid.grid_rows?.find(row => {
              const wrapper = row.wrapper || row.$wrapper;
              return (wrapper?.[0] || wrapper)?.contains?.(event.target);
            });
            const rowIndex = (frm.doc[table] || []).findIndex(row =>
              row === gridRow?.doc || (rowElement?.dataset.name && row.name === rowElement.dataset.name));
            let singleColumn;
            try {
              singleColumn = parsePaste(text).every(row => row.length === 1);
            } catch (error) {
              frappe.msgprint(esc(error.message));
              return;
            }
            if (singleColumn && table !== 'accessorise_table' && cell && rowIndex >= 0 && materialColumns.includes(cell.dataset.fieldname)) {
              pasteIntoCells(frm, table, rowIndex, cell.dataset.fieldname, text)
                .catch(error => frappe.msgprint(esc(error.message)));
              return;
            }
            openImport(frm, table, text);
          }, true);
        });
      }
      const rows = frm.doc.accessorise_table || [];
      const matched = rows.filter(r => r.item).length;
      if (rows.length) frm.dashboard.add_indicator(__('Accessories mapped: {0} of {1}', [matched, rows.length]), matched === rows.length ? 'green' : 'orange');
      if (frm.doc.docstatus === 1 && rows.length && ['Stock User', 'Stock Manager', 'System Manager'].some(r => frappe.user_roles.includes(r))) {
        frm.add_custom_button(__('Map Accessories'), () => openMapping(frm));
      }
    },
  });
  if (typeof module !== 'undefined') module.exports = {parsePaste, column, populatedColumns, sectionType, detectSections, sectionRange, isEmptyImportRow, prepareCellPaste, pasteIntoCells};
})();
