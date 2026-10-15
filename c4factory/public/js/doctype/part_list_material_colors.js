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
for (const parentType of ['Part List', 'Production Order']) {
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
  const result = material ? await frappe.db.get_value('Part Material', material, ['color_palette', 'color']) : null;
  if (sharedPartMaterialColorRequests.get(cdn) !== request || row.material !== material || locals[cdt]?.[cdn] !== row) return;
  const palette = result?.message?.color_palette || null;
  // Await the palette change handler before applying the material's default color.
  await frappe.model.set_value(cdt, cdn, 'color_palette', palette);
  if (sharedPartMaterialColorRequests.get(cdn) !== request || row.material !== material) return;
  await frappe.model.set_value(cdt, cdn, 'color_doctype', palette ? 'Material Color' : null);
  const color = result?.message?.color;
  if (palette && color) {
    const selected = await frappe.db.get_value('Material Color', color, 'palette');
    if (sharedPartMaterialColorRequests.get(cdn) !== request || row.material !== material || row.color_palette !== palette) return;
    if (selected?.message?.palette === palette) {
      await frappe.model.set_value(cdt, cdn, 'basic_color', color);
    }
  }
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
