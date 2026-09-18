async function calculate_bom_item_qty(frm, cdt, cdn) {
  const row = frappe.get_doc(cdt, cdn);
  const factors = ["custom_unit_qty", "custom_width", "custom_height", "custom_depth"];
  for (const field of factors) {
    if (row[field] == null || row[field] === "") {
      await frappe.model.set_value(cdt, cdn, field, 1);
    }
  }
  const qty = factors.reduce((value, field) => value * flt(row[field]), 1);
  return frappe.model.set_value(cdt, cdn, "qty", flt(qty, precision("qty", row)));
}

frappe.ui.form.on("BOM Item", {
  items_add: calculate_bom_item_qty,
  custom_unit_qty: calculate_bom_item_qty,
  custom_width: calculate_bom_item_qty,
  custom_height: calculate_bom_item_qty,
  custom_depth: calculate_bom_item_qty,

  async item_code(frm, cdt, cdn) {
    await calculate_bom_item_qty(frm, cdt, cdn);
    const row = frappe.get_doc(cdt, cdn);
    if (!row.item_code) return;
    const item_code = row.item_code;
    return frappe.call({
      method: "frappe.client.get_value",
      args: {
        doctype: "Item",
        filters: { name: item_code },
        fieldname: ["custom_techniacl_uom", "stock_uom"],
      },
      async callback(res) {
        if (!res || !res.message || row.item_code !== item_code) return;
        if (res.message.custom_techniacl_uom) {
          await frappe.model.set_value(cdt, cdn, "uom", res.message.custom_techniacl_uom);
        }
        if (res.message.stock_uom) {
          await frappe.model.set_value(cdt, cdn, "stock_uom", res.message.stock_uom);
        }
        await calculate_bom_item_qty(frm, cdt, cdn);
      },
    });
  },
});
