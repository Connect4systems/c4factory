// Rebind on refresh as well as setup: other app scripts can replace grid queries.
function configurePartMaterialColors(frm) {
  for (const field of (frm.meta?.fields || []).filter(f => f.fieldtype === 'Table' && f.options === 'Part List Materials')) {
    const grid = frm.fields_dict[field.fieldname]?.grid;
    if (!grid) continue;
    // Also override stale Dynamic Link metadata from older site customizations.
    grid.update_docfield_property('basic_color', 'fieldtype', 'Link');
    grid.update_docfield_property('basic_color', 'options', 'Material Color');
    frm.set_query('basic_color', field.fieldname, (doc, cdt, cdn) => {
      const row = locals[cdt][cdn];
      return {
        query: 'c4factory.api.part_list_material_colors.material_color_query',
        filters: {palette: row.color_palette || '', material: row.material || ''},
      };
    });
  }
}
for (const parentType of ['Part List', 'Part Bundle', 'Production Order']) {
  frappe.ui.form.on(parentType, {
    setup: configurePartMaterialColors,
    refresh: configurePartMaterialColors,
  });
}
const sharedPartMaterialColorRequests = new Map();
async function syncSharedPartMaterialColor(frm, cdt, cdn) {
  const row = locals[cdt]?.[cdn];
  if (!row) return;
  const material = row.material;
  const request = {};
  sharedPartMaterialColorRequests.set(cdn, request);
  await frappe.model.set_value(cdt, cdn, 'basic_color', null);
  await frappe.model.set_value(cdt, cdn, 'color_palette', null);
  const result = material ? await frappe.db.get_value('Part Material', material, 'color_palette') : null;
  if (sharedPartMaterialColorRequests.get(cdn) !== request || row.material !== material || locals[cdt]?.[cdn] !== row) return;
  const prefix = frm.doc.doctype === 'Part List' ? {panel_materials: 'panel', metal_material: 'metal', other_material: 'other'}[row.parentfield] : null;
  const palette = (prefix && frm.doc[prefix + '_color_palette']) || result?.message?.color_palette || null;
  // Await the palette change handler before enabling color selection.
  await frappe.model.set_value(cdt, cdn, 'color_palette', palette);
  if (sharedPartMaterialColorRequests.get(cdn) !== request || row.material !== material) return;
  await frappe.model.set_value(cdt, cdn, 'color_doctype', palette ? 'Material Color' : null);
  if (prefix && frm.doc[prefix + '_color_palette'] === palette && frm.doc[prefix + '_base_color'])
    await frappe.model.set_value(cdt, cdn, 'basic_color', frm.doc[prefix + '_base_color']);
  frm.refresh_field(row.parentfield);
}
frappe.ui.form.on('Part List Materials', {
  material: syncSharedPartMaterialColor,
  async color_palette(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    await frappe.model.set_value(cdt, cdn, 'basic_color', null);
    await frappe.model.set_value(cdt, cdn, 'color_doctype', row.color_palette ? 'Material Color' : null);
  },
});

// Each section has its own palette and default color. Refresh only binds queries.
const partListColorSections = {panel: 'panel_materials', metal: 'metal_material', other: 'other_material'};
const partListHeaderEvents = {
  setup(frm) {
    for (const prefix of Object.keys(partListColorSections)) {
      frm.set_query(prefix + '_base_color', () => ({
        query: 'c4factory.api.part_list_material_colors.material_color_query',
        filters: {palette: frm.doc[prefix + '_color_palette'] || ''},
      }));
    }
  },
};
for (const [prefix, table] of Object.entries(partListColorSections)) {
  partListHeaderEvents[prefix + '_color_palette'] = async frm => {
    if (frm._applyingPartListCopy || frm.doc.docstatus !== 0 || frm.read_only) return;
    const palette = frm.doc[prefix + '_color_palette'] || null;
    frm.doc[prefix + '_base_color'] = null;
    frm.refresh_field(prefix + '_base_color');
    const checks = await Promise.all((frm.doc[table] || []).map(async row => {
      const result = row.basic_color ? await frappe.db.get_value('Material Color', row.basic_color, 'palette') : null;
      return {row, color: row.basic_color, valid: !!palette && result?.message?.palette === palette};
    }));
    if ((frm.doc[prefix + '_color_palette'] || null) !== palette) return;
    for (const {row, color, valid} of checks) {
      row.color_palette = palette;
      row.color_doctype = palette ? 'Material Color' : null;
      if (!valid && row.basic_color === color) row.basic_color = null;
    }
    frm.refresh_field(table);
    frm.dirty();
  };
  partListHeaderEvents[prefix + '_base_color'] = frm => {
    if (frm._applyingPartListCopy || frm.doc.docstatus !== 0 || frm.read_only) return;
    for (const row of frm.doc[table] || []) {
      row.color_palette = frm.doc[prefix + '_color_palette'] || null;
      row.color_doctype = row.color_palette ? 'Material Color' : null;
      row.basic_color = frm.doc[prefix + '_base_color'] || null;
    }
    frm.refresh_field(table);
    frm.dirty();
  };
}
frappe.ui.form.on('Part List', partListHeaderEvents);
