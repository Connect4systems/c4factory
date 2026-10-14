// Keep conversions in Item.uoms so standard buying, selling and stock flows use them.
frappe.ui.form.on("Item", {
	refresh(frm) {
		c4factory_item_uom_help(frm);
	},
	stock_uom(frm) {
		c4factory_item_uom_help(frm);
	}
});

function c4factory_item_uom_help(frm) {
	if (!frm.fields_dict.uoms || !frm.fields_dict.stock_uom) return;
	frm.set_df_property("stock_uom", "description",
		__("Default UOM used to track this item's stock."));
	frm.set_df_property("uoms", "description",
		__("Conversion Factor is the number of default units in 1 of the selected UOM, for this item. Example: default UOM Piece, UOM Kilogram, factor 300 means 1 kg = 300 pieces. Reuse Kilogram for other items with their own factors."));
	const grid = frm.fields_dict.uoms.grid;
	grid.update_docfield_property("conversion_factor", "description",
		__("Number of this item's default units in 1 of this UOM. Must be greater than zero; the default UOM has factor 1."));
}
