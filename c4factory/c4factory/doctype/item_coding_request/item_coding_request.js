// Copyright (c) 2026, Connect 4 Systems and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item Coding Request", {
  before_submit(frm) {
    if (!frm.doc.item_code) {
      frappe.throw(__("Item Code is required before submitting an Item Coding Request."));
    }
  },
});
