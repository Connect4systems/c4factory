"""Headless row-tab regression with a small Frappe/Bootstrap behavior adapter.

Run: python tests/item_specs_tabs_ui.py
Checks DOM tab isolation and initial activation, not a deployed Frappe site.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

ADAPTER = r"""() => {
  window.frappe = {ui: {form: {}}};
  function wrap(element) {
    return {
      element,
      find: selector => wrap(element.querySelector(selector)),
      attr(values) {for (const [key, value] of Object.entries(values)) element.setAttribute(key, value);},
    };
  }
  function makeTab(layout, df) {
    const id = layout.frm.doctype.replaceAll(' ', '-').toLowerCase() + '-' + df.fieldname;
    const li = document.createElement('li');
    li.innerHTML = `<button class="nav-link" id="${id}-tab" href="#${id}">${df.label}</button>`;
    const pane = document.createElement('div');
    pane.className = 'tab-pane'; pane.id = id;
    pane.textContent = df.label === 'Spcs' ? 'Panel | Metal | Other' : 'Item Code, Quantity';
    layout.links.appendChild(li); layout.content.appendChild(pane);
    const tab = {
      df, frm: layout.frm, hidden: false, tab_link: wrap(li), wrapper: wrap(pane),
      is_hidden() {return this.hidden;},
      set_active() {
        const target = document.querySelector(li.querySelector('button').getAttribute('href'));
        for (const sibling of layout.content.children) sibling.classList.remove('active');
        target.classList.add('active');
        this.frm.set_active_tab(this);
      },
    };
    li.querySelector('button').addEventListener('click', () => tab.set_active());
    return tab;
  }
  frappe.ui.form.Layout = class {
    constructor(options) {
      Object.assign(this, options); this.tabs = [];
      this.wrapper = document.createElement('section');
      this.wrapper.innerHTML = '<ul></ul><div class="tab-content"></div>';
      document.body.appendChild(this.wrapper);
      this.links = this.wrapper.querySelector('ul');
      this.content = this.wrapper.querySelector('.tab-content');
    }
    make_tab(df) {const tab = makeTab(this, df); this.tabs.push(tab); return tab;}
    set_tab_as_active() {
      const previous = this.frm.get_active_tab();
      if (previous) previous.set_active();
      else this.tabs.find(tab => !tab.is_hidden())?.set_active();
    }
  };
  window.build = (type, frm, parent = false) => {
    const layout = new frappe.ui.form.Layout({frm, grid: parent ? null : {df: {options: type}}});
    layout.make_tab({fieldname: '__details', label: 'Details'});
    layout.make_tab({fieldname: 'spcs_tab', label: 'Spcs'});
    layout.set_tab_as_active();
    return layout;
  };
  window.frm = {doctype: 'Sales Order', get_active_tab() {return this.active_tab;},
    set_active_tab(tab) {this.active_tab = tab;}};
  window.parentLayout = build(null, frm, true);
} """


def main():
	with sync_playwright() as playwright:
		browser = playwright.chromium.launch(headless=True)
		page = browser.new_page()
		page.set_content("<style>.tab-pane {display:none}.tab-pane.active {display:block}</style>")
		page.evaluate(ADAPTER)
		# Reproduce the framework behavior: parent has an active tab, child stays blank.
		assert page.evaluate("""() => {
          const broken = build('Sales Order Item', frm);
          const empty = !broken.content.querySelector('.active');
          broken.wrapper.remove(); return empty;
        }""")
		script = (ROOT / "c4factory/public/js/doctype/item_specs_tabs.js").read_text()
		page.add_script_tag(content=script)
		page.add_script_tag(content=script)  # Global asset reload must not wrap twice.
		for doctype in ("Sales Order Item", "PDS Request Item", "Project BOQ Item"):
			page.evaluate("type => { window.row = build(type, frm); }", doctype)
			pane = page.locator("section").last
			assert pane.locator(".tab-pane.active").inner_text() == "Item Code, Quantity"
			pane.get_by_role("button", name="Spcs", exact=True).click()
			assert pane.locator(".tab-pane.active").inner_text() == "Panel | Metal | Other"
			assert page.evaluate("frm.active_tab === parentLayout.tabs[0]")
			# Refresh preserves the row selection; another row starts on Details.
			page.evaluate("row.set_tab_as_active()")
			assert pane.locator(".tab-pane.active").inner_text() == "Panel | Metal | Other"
			page.evaluate("type => { window.other = build(type, frm); }", doctype)
			assert page.locator("section").last.locator(".tab-pane.active").inner_text() == "Item Code, Quantity"
			# A remembered tab becoming hidden must fall back to Details.
			page.evaluate("row.tabs[1].hidden = true; row.set_tab_as_active()")
			assert pane.locator(".tab-pane.active").inner_text() == "Item Code, Quantity"
		assert page.evaluate("""() => {
          const ids = [...document.querySelectorAll('[id]')].map(element => element.id);
          return ids.length === new Set(ids).size;
        }""")
		# Parent forms and unrelated child tables retain the framework's behavior.
		assert page.evaluate("""() => {
          const unrelated = build('Delivery Note Item', frm);
          return !unrelated.content.querySelector('.active') && frm.active_tab === parentLayout.tabs[0];
        }""")
		browser.close()
	print("PASS: all three child editors open Details, switch tabs, refresh, and keep parent/row state isolated")


if __name__ == "__main__":
	main()
