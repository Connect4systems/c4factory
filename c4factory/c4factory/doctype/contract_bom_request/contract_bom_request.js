// Copyright (c) 2025, Connect 4 Systems and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract BOM Request", {
	setup(frm) {
		frm.set_query("bom", "items", (doc, cdt, cdn) => ({
			query: "c4factory.c4factory.doctype.contract_bom_request.contract_bom_request.get_item_boms",
			filters: { item: locals[cdt][cdn].item, sales_order: doc.sales_order }
		}));
	},
	refresh(frm) {
		frm.fields_dict.items.grid.update_docfield_property("create_bom", "read_only", frm.doc.docstatus !== 0);
	}
});

frappe.ui.form.on("Contract BOM Item", {
	item(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "bom", null);
	},
	async create_bom(frm, cdt, cdn) {
		if (frm.doc.docstatus !== 0) {
			frappe.msgprint(__("BOM links can only be changed on a draft Contract BOM Request."));
			return;
		}
		const row = locals[cdt][cdn];
		if (!row.item) {
			frappe.msgprint(__("Please set an Item in the row before creating a BOM."));
			return;
		}
		if (frm.__creating_contract_bom) return;
		frm.__creating_contract_bom = true;
		try {
			if (row.bom) {
				const confirmed = await new Promise(resolve => frappe.confirm(
					__("A BOM already exists for this row ({0}). Create a new one anyway?", [row.bom]),
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
				method: "c4factory.c4factory.doctype.contract_bom_request.contract_bom_request.create_bom_for_item",
				args: {
					item: savedRow.item,
					qty: savedRow.qty || 1,
					contract_bom_request: frm.doc.name,
					contract_bom_item: savedRow.name
				},
				freeze: true,
				freeze_message: __("Creating BOM...")
			});
			if (result.message) {
				await frm.reload_doc();
				if (frm.dashboard && frm.dashboard.set_open_count) frm.dashboard.set_open_count();
				frappe.show_alert({
					message: __("BOM {0} created and linked.", [result.message]),
					indicator: "green"
				});
			}
		} finally {
			frm.__creating_contract_bom = false;
		}
	}
});
