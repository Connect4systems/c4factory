// Link filters are resolved per row so all material tables can use different palettes.
for (const parentType of ['Part List', 'Production Order']) {
  frappe.ui.form.on(parentType, {
    setup(frm) {
      for (const field of frm.meta.fields.filter(f => f.fieldtype === 'Table' && f.options === 'Part List Materials')) {
        frm.set_query('basic_color', field.fieldname, (doc, cdt, cdn) => ({
          filters: { palette: locals[cdt][cdn].color_palette || '' },
        }));
      }
    },
  });
}
const sharedPartMaterialColorRequests = new Map();
async function syncSharedPartMaterialColor(frm, cdt, cdn) {
  const row = locals[cdt]?.[cdn];
  if (!row) return;
  const material = row.material;
  const request = {};
  sharedPartMaterialColorRequests.set(cdn, request);
  await frappe.model.set_value(cdt, cdn, {basic_color: null, color_palette: null, color_doctype: null});
  const result = material ? await frappe.db.get_value('Part Material', material, ['color_palette', 'color']) : null;
  if (sharedPartMaterialColorRequests.get(cdn) !== request || row.material !== material || locals[cdt]?.[cdn] !== row) return;
  const palette = result?.message?.color_palette || null;
  await frappe.model.set_value(cdt, cdn, {color_palette: palette, color_doctype: palette ? 'Material Color' : null, basic_color: result?.message?.color || null});
}
frappe.ui.form.on('Part List Materials', {
  material: syncSharedPartMaterialColor,
  async color_palette(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    await frappe.model.set_value(cdt, cdn, {basic_color: null, color_doctype: row.color_palette ? 'Material Color' : null});
  },
});
