frappe.ui.form.on("Item", {
	refresh(frm) {
		return sync_material_color(frm, false);
	},
	item_group(frm) {
		return sync_material_color(frm, true);
	}
});

async function sync_material_color(frm, clear) {
	if (!frm.fields_dict.custom_material_color) return;
	const group = frm.doc.item_group;
	const request = (frm.__material_color_request || 0) + 1;
	frm.__material_color_request = request;
	frm.set_df_property("custom_material_color", "read_only", 1);
	if (clear) await frm.set_value("custom_material_color", null);
	const result = group
		? await frappe.db.get_value("Item Group", group, "custom_color")
		: null;
	if (request !== frm.__material_color_request || group !== frm.doc.item_group) return;
	const target = (result && result.message && result.message.custom_color) || null;
	if (!target || frm.doc.custom_material_color_doctype !== target) {
		await frm.set_value("custom_material_color", null);
	}
	await frm.set_value("custom_material_color_doctype", target);
	frm.set_df_property("custom_material_color", "read_only", !target);
	frm.refresh_field("custom_material_color");
}
