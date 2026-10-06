// Copyright (c) 2026, Connect 4 Systems and contributors
// For license information, please see license.txt

frappe.ui.form.on("Part Material", {
	setup(frm) {
		frm.set_query("color", () => ({ filters: { istable: 0, issingle: 0 } }));
	}
});
