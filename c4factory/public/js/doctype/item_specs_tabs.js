/* global frappe */
(() => {
	const Layout = frappe.ui.form.Layout;
	if (Layout.prototype._c4factory_item_specs_tabs) return;
	Layout.prototype._c4factory_item_specs_tabs = true;
	const child_types = new Set(["Sales Order Item", "PDS Request Item", "Project BOQ Item"]);
	const make_tab = Layout.prototype.make_tab;
	const set_tab_as_active = Layout.prototype.set_tab_as_active;
	let next_layout_id = 0;

	function is_specs_row(layout) {
		return child_types.has(layout.grid?.df?.options);
	}

	Layout.prototype.make_tab = function (df) {
		const tab = make_tab.call(this, df);
		if (!is_specs_row(this)) return tab;

		// Frappe otherwise uses the parent doctype for every child tab's DOM ID.
		this._c4factory_tab_id ||= ++next_layout_id;
		const id = `c4factory-row-tab-${this._c4factory_tab_id}-${this.tabs.length}`;
		tab.tab_link.find(".nav-link").attr({
			id: `${id}-tab`, href: `#${id}`, "aria-controls": id,
		});
		tab.wrapper.attr({id, "aria-labelledby": `${id}-tab`});

		// Tab listeners must remember this row's selection, not change the parent form.
		tab.frm = Object.create(this.frm);
		tab.frm.set_active_tab = selected => { this._c4factory_active_tab = selected; };
		return tab;
	};

	Layout.prototype.set_tab_as_active = function () {
		if (!is_specs_row(this)) return set_tab_as_active.call(this);
		const previous = this._c4factory_active_tab;
		const selected = this.tabs.includes(previous) && !previous.is_hidden()
			? previous : this.tabs.find(tab => !tab.is_hidden());
		selected?.set_active();
	};
})();
