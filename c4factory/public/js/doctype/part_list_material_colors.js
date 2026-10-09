const sharedPartMaterialColorRequests = new Map();

function partListTableColorDefault(frm, row) {
  if (frm.doc.doctype !== "Part List") return null;
  if (row.parentfield === "panel_materials") {
    return {
      target: { "Artificial Wood": "P-Wood", "Natural Wood": "P-Natural" }[frm.doc.wood_type || "Artificial Wood"],
      color: frm.doc.wood_color || null,
    };
  }
  if (row.parentfield === "metal_material") return { target: "P-Metal", color: frm.doc.metal_color || null };
  return null;
}

async function applyPartListTableColor(frm, field) {
  for (const row of frm.doc[field] || []) {
    const value = partListTableColorDefault(frm, row);
    if (!value) continue;
    // Invalidate a pending material lookup before applying the header choice.
    sharedPartMaterialColorRequests.set(row.name, (sharedPartMaterialColorRequests.get(row.name) || 0) + 1);
    await frappe.model.set_value(row.doctype, row.name, {
      color_doctype: value.target || null, basic_color: value.color,
    });
  }
  frm.refresh_field(field);
}

async function syncSharedPartMaterialColor(frm, cdt, cdn, clear = false) {
  const row = locals[cdt]?.[cdn];
  if (!row) return;
  const material = row.material;
  const request = (sharedPartMaterialColorRequests.get(cdn) || 0) + 1;
  sharedPartMaterialColorRequests.set(cdn, request);
  if (clear) {
    await frappe.model.set_value(cdt, cdn, { basic_color: null, color_doctype: null });
  }
  const tableDefault = partListTableColorDefault(frm, row);
  const result = !tableDefault && material
    ? await frappe.db.get_value("Part Material", material, "color")
    : null;
  if (sharedPartMaterialColorRequests.get(cdn) !== request || row.material !== material || locals[cdt]?.[cdn] !== row) return;
  const target = tableDefault?.target || result?.message?.color || null;
  if (!target || row.color_doctype !== target) {
    await frappe.model.set_value(cdt, cdn, "basic_color", null);
  }
  await frappe.model.set_value(cdt, cdn, "color_doctype", target);
  if (tableDefault && clear) {
    await frappe.model.set_value(cdt, cdn, "basic_color", tableDefault.color);
  }
  frm.refresh_field(row.parentfield || "pick_list_materials");
}

function refreshSharedPartMaterialColors(frm) {
  return Promise.all((frm.meta.fields || [])
    .filter(field => field.fieldtype === "Table" && field.options === "Part List Materials")
    .flatMap(field => (frm.doc[field.fieldname] || []).map(row =>
      syncSharedPartMaterialColor(frm, row.doctype, row.name))));
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
  form_render(frm, cdt, cdn) {
    return syncSharedPartMaterialColor(frm, cdt, cdn);
  },
});

frappe.ui.form.on("Part List", {
  wood_color(frm) { return applyPartListTableColor(frm, "panel_materials"); },
  metal_color(frm) { return applyPartListTableColor(frm, "metal_material"); },
  wood_type(frm) { return refreshSharedPartMaterialColors(frm); },
});

for (const parent of ["Part List", "Color sample"]) {
  frappe.ui.form.on(parent, { refresh: refreshSharedPartMaterialColors });
}
