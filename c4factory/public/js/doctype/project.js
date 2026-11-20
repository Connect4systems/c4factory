/* global frappe, __, flt */
(() => {
	const api = "c4factory.api.project_boq.";

	function quantity_dialog(frm, rows, installation_row = null) {
		if (!rows.length) {
			frappe.msgprint(__("No remaining quantity is available."));
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: installation_row ? __("Create Installation Note") : __("Create Delivery Note"),
			size: "large",
			fields: [{
				fieldname: "rows", fieldtype: "Table", label: __("Selected Items"),
				cannot_add_rows: true, cannot_delete_rows: true, in_place_edit: true,
				fields: [
					{fieldname: "source", fieldtype: "Data", hidden: 1},
					{fieldname: "item_code", fieldtype: "Data", label: __("Item"), read_only: 1, in_list_view: 1},
					{fieldname: "delivery_note", fieldtype: "Link", options: "Delivery Note", label: __("Delivery Note"), read_only: 1, in_list_view: !!installation_row},
					{fieldname: "remaining", fieldtype: "Float", label: __("Available Qty"), read_only: 1, in_list_view: 1},
					{fieldname: "qty", fieldtype: "Float", label: __("Quantity"), in_list_view: 1},
				],
				data: rows.map(r => ({...r, remaining: r.qty})),
			}],
			primary_action_label: __("Create Draft"),
			async primary_action(values) {
				const selected = (values.rows || []).filter(r => flt(r.qty) > 0);
				if (!selected.length || selected.some(r => flt(r.qty) > flt(r.remaining))) {
					frappe.msgprint(__("Enter quantities within the available quantity for at least one row."));
					return;
				}
				dialog.get_primary_btn().prop("disabled", true);
				try {
					const response = await frappe.call({
						method: api + (installation_row ? "create_installation_note" : "create_delivery_note"),
						args: {
							project: frm.doc.name,
							...(installation_row ? {sales_order_item: installation_row.sales_order_item} : {}),
							rows: selected.map(r => ({sales_order_item: r.source, qty: r.qty})),
						}, freeze: true,
					});
					dialog.hide();
					frappe.set_route("Form", installation_row ? "Installation Note" : "Delivery Note", response.message);
				} finally {
					dialog.get_primary_btn().prop("disabled", false);
				}
			},
		});
		dialog.show();
	}

	function deliver(frm, rows) {
		if (!rows.length) {
			frappe.msgprint(__("Select BOQ rows to deliver."));
			return;
		}
		quantity_dialog(frm, rows.filter(r => flt(r.actual_qty) > flt(r.delivered_qty)).map(r => ({
			source: r.sales_order_item, item_code: r.item_code, qty: flt(r.actual_qty) - flt(r.delivered_qty),
		})));
	}

	frappe.ui.form.on("Project", {
		refresh(frm) {
			if (frm.is_new() || !frm.doc.sales_order) return;
			const grid = frm.fields_dict.custom_project_boq.grid;
			grid.cannot_add_rows = true;
			grid.cannot_delete_rows = true;
			const live = frm.doc.__onload && frm.doc.__onload.project_boq;
			if (live) {
				// Display current transactions without marking the Project as edited.
				frm.doc.custom_project_boq = live.map((row, idx) => ({
					...row, doctype: "Project BOQ Item", name: `boq-${idx}-${frm.doc.name}`,
					parent: frm.doc.name, parenttype: "Project", parentfield: "custom_project_boq", idx: idx + 1,
				}));
				locals["Project BOQ Item"] = locals["Project BOQ Item"] || {};
				frm.doc.custom_project_boq.forEach(row => { locals["Project BOQ Item"][row.name] = row; });
				frm.refresh_field("custom_project_boq");
			}
			if (frm.doc.__onload && frm.doc.__onload.project_boq_active) {
				frm.add_custom_button(__("Create Delivery Note"), () => {
					const selected = frm.fields_dict.custom_project_boq.grid.get_selected_children();
					deliver(frm, selected);
				});
			}
			frm.add_custom_button(__("Refresh BOQ"), () => frm.reload_doc());
		},
	});

	frappe.ui.form.on("Project BOQ Item", {
		create_delivery(frm, cdt, cdn) { deliver(frm, [locals[cdt][cdn]]); },
		async create_installation_note(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			const response = await frappe.call({method: api + "installation_options", args: {
				project: frm.doc.name, sales_order_item: row.sales_order_item,
			}});
			quantity_dialog(frm, (response.message || []).map(r => ({...r, source: r.delivery_note_item})), row);
		},
	});
})();
