const sharedPartMaterialColorRequests = new Map();

async function syncSharedPartMaterialColor(frm, cdt, cdn, clear = false) {
  const row = locals[cdt]?.[cdn];
  if (!row) return;
  const material = row.material;
  const request = (sharedPartMaterialColorRequests.get(cdn) || 0) + 1;
  sharedPartMaterialColorRequests.set(cdn, request);
  if (clear) {
    await frappe.model.set_value(cdt, cdn, { basic_color: null, color_doctype: null });
  }
  const result = material
    ? await frappe.db.get_value("Part Material", material, "color")
    : null;
  if (sharedPartMaterialColorRequests.get(cdn) !== request || row.material !== material || locals[cdt]?.[cdn] !== row) return;
  const target = result?.message?.color || null;
  if (!target || row.color_doctype !== target) {
    await frappe.model.set_value(cdt, cdn, "basic_color", null);
  }
  await frappe.model.set_value(cdt, cdn, "color_doctype", target);
  frm.refresh_field(row.parentfield || "pick_list_materials");
}

function refreshSharedPartMaterialColors(frm) {
  return Promise.all((frm.meta.fields || [])
    .filter(field => field.fieldtype === "Table" && field.options === "Part List Materials")
    .flatMap(field => (frm.doc[field.fieldname] || []).map(row =>
      syncSharedPartMaterialColor(frm, row.doctype, row.name))));
}

frappe.ui.form.on("Part List Materials", {
  material(frm, cdt, cdn) {
    return syncSharedPartMaterialColor(frm, cdt, cdn, true);
  },
  form_render(frm, cdt, cdn) {
    return syncSharedPartMaterialColor(frm, cdt, cdn);
  },
});

for (const parent of ["Part List", "Color sample"]) {
  frappe.ui.form.on(parent, { refresh: refreshSharedPartMaterialColors });
}
