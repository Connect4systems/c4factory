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
  if ((!target || row.color_doctype !== target) && row.basic_color) {
    await frappe.model.set_value(cdt, cdn, "basic_color", null);
  }
  // Frappe treats an empty string and null as different values. Avoid dirtying
  // saved documents on refresh when both represent an empty color source.
  if ((row.color_doctype || null) !== target) {
    await frappe.model.set_value(cdt, cdn, "color_doctype", target);
  }
  frm.refresh_field(row.parentfield || "pick_list_materials");
}

frappe.ui.form.on("Part List Materials", {
  panel_materials_add(frm, cdt, cdn) {
    return syncSharedPartMaterialColor(frm, cdt, cdn, true);
  },
  metal_material_add(frm, cdt, cdn) {
    return syncSharedPartMaterialColor(frm, cdt, cdn, true);
  },
  material(frm, cdt, cdn) {
    return syncSharedPartMaterialColor(frm, cdt, cdn, true);
  },
  other_material_add(frm, cdt, cdn) {
    return syncSharedPartMaterialColor(frm, cdt, cdn, true);
  },
});
