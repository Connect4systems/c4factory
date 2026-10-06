// Copyright (c) 2025, Connect 4 Systems and contributors
// For license information, please see license.txt

frappe.ui.form.on("PDS Request", {
	setup(frm) {
		frm.set_query("part_list", "items", (doc, cdt, cdn) => ({
			query: "c4factory.c4factory.doctype.pds_request.pds_request.get_item_part_lists",
			filters: { item: locals[cdt][cdn].item, sales_order: doc.sales_order }
		}));
	},
	refresh(frm) {
		frm.fields_dict.items.grid.update_docfield_property("create_part_list", "read_only", frm.doc.docstatus !== 0);
	}
});

frappe.ui.form.on("PDS Request Item", {
	item(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "part_list", null);
	},
	async create_part_list(frm, cdt, cdn) {
		if (frm.doc.docstatus !== 0) {
			frappe.msgprint(__("Part List links can only be changed on a draft PDS Request."));
			return;
		}
		const row = locals[cdt][cdn];
		if (!row.item) {
			frappe.msgprint(__("Please set an Item in the row before creating a Part List."));
			return;
		}
		if (frm.__creating_pds) return;
		frm.__creating_pds = true;
		try {
			if (row.part_list) {
				const confirmed = await new Promise(resolve => frappe.confirm(
					__("A Part List already exists for this row ({0}). Create a new one anyway?", [row.part_list]),
					() => resolve(true), () => resolve(false)
				));
				if (!confirmed) return;
			}
			const rowIndex = frm.doc.items.indexOf(row);
			if (frm.is_new() || frm.is_dirty()) await frm.save();
			if (frm.is_new() || frm.is_dirty()) return;
			const savedRow = frm.doc.items[rowIndex];
			if (!savedRow || savedRow.item !== row.item) return;
			const result = await frappe.call({
				method: "c4factory.c4factory.doctype.pds_request.pds_request.create_part_list_for_item",
				args: {
					item: savedRow.item,
					qty: savedRow.qty || 1,
					pds_request: frm.doc.name,
					pds_request_item: savedRow.name
				},
				freeze: true,
				freeze_message: __("Creating Part List...")
			});
			if (result.message) {
				await frm.reload_doc();
				if (frm.dashboard && frm.dashboard.set_open_count) frm.dashboard.set_open_count();
				frappe.show_alert({
					message: __("Part List {0} created and linked.", [result.message]),
					indicator: "green"
				});
			}
		} finally {
			frm.__creating_pds = false;
		}
	}
});
