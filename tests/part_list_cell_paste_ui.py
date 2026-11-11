"""Run with python tests/part_list_cell_paste_ui.py."""
from pathlib import Path

from playwright.sync_api import sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page()
    page.evaluate("""() => {
      window.__ = (text, args=[]) => text.replace(/\{(\d+)\}/g, (_, n) => args[n]);
      window.module = {exports: {}};
      window.pasteHandlers = {};
      window.frappe = {utils: {escape_html: String}, ui: {form: {on(type, events) {pasteHandlers[type] = events;}}}};
    }""")
    page.add_script_tag(path=str(Path(__file__).resolve().parents[1] / "c4factory/public/js/doctype/part_list_import.js"))
    page.evaluate("""async () => {
      const {prepareCellPaste, pasteIntoCells} = module.exports;
      const assert = (ok, message) => {if (!ok) throw Error(message);};
      const parsed = prepareCellPaste('10\\n20\\n', 'width');
      assert(parsed.length === 2 && parsed[1].width === 20, 'single column');
      const full = prepareCellPaste('Panel A\\tلوح\\t100\\t50\\t20\\t18\\t2\\tMDF\\tTest note\\t1\\tOak', 'part_name')[0];
      assert(full.part_name === 'Panel A' && full.part_name_ar === 'لوح' && full.lenght === 100 && full.qty === 2 && full.material === 'MDF' && full.note === 'Test note' && full.edite_color === 1 && full.basic_color === 'Oak', 'standard Excel sequence');
      assert(prepareCellPaste('"a\\nb"', 'note')[0].note === 'a\\nb', 'quoted cell');
      for (const [text, field] of [['abc', 'width'], ['x\\ty', 'basic_color'], ['maybe', 'edite_color']]) {
        let rejected = false;
        try {prepareCellPaste(text, field);} catch (_) {rejected = true;}
        assert(rejected, 'invalid paste rejected');
      }
      const first = {doctype: 'Part List Materials', name: 'r1', part_name: 'Keep', width: 5};
      const frm = {doc: {docstatus: 0, panel_materials: [first]},
        add_child(table) {const row = {doctype: first.doctype, name: 'r' + (this.doc[table].length+1)};this.doc[table].push(row);return row;},
        dirty() {this.changed = true;}, refresh_field() {}};
      frappe.model = {async set_value(type, name, field, value) {
        frm.doc.panel_materials.find(row => row.name === name)[field] = value;
      }};
      await pasteIntoCells(frm, 'panel_materials', 0, 'width', '10\\n20');
      assert(first.width === 10 && first.part_name === 'Keep', 'existing row retained');
      assert(frm.doc.panel_materials[1].width === 20 && frm.changed, 'extra rows added');
      await pasteIntoCells(frm, 'panel_materials', 0, 'width', '30\\t40');
      assert(first.width === 30 && first.hight === 40, 'rectangular paste');
      frm.doc.docstatus = 1;
      await pasteIntoCells(frm, 'panel_materials', 0, 'width', '99');
      assert(first.width === 30, 'submitted document unchanged');
    }""")
    page.evaluate(r"""async () => {
      const assert = (ok, message) => {if (!ok) throw Error(message);};
      const root = document.createElement('div');
      root.innerHTML = '<div class="grid-row" data-name="r2"><div data-fieldname="width"><input></div></div>';
      document.body.append(root);
      const rows = [
        {doctype: 'Part List Materials', name: 'r1', width: 5},
        {doctype: 'Part List Materials', name: 'r2', width: 6, part_name: 'Keep'},
      ];
      const frm = {doc: {docstatus: 0, panel_materials: rows},
        fields_dict: {panel_materials: {grid: {wrapper: [root], grid_rows: []}}},
        add_custom_button() {}, dirty() {}, refresh_field() {},
        add_child(table) {const row = {doctype: rows[0].doctype, name: 'r' + (rows.length + 1)}; rows.push(row); return row;},
      };
      frappe.model = {async set_value(type, name, field, value) {rows.find(row => row.name === name)[field] = value;}};
      frappe.msgprint = message => {throw Error(message);};
      pasteHandlers['Part List'].refresh(frm);
      const paste = text => {
        const clipboardData = new DataTransfer(); clipboardData.setData('text/plain', text);
        root.querySelector('input').dispatchEvent(new ClipboardEvent('paste', {bubbles: true, cancelable: true, clipboardData}));
      };
      paste('10\n20\n');
      await new Promise(resolve => setTimeout(resolve, 0));
      assert(rows[0].width === 5 && rows[1].width === 10 && rows[2].width === 20, 'column paste starts at clicked row and adds rows');
      assert(rows[1].part_name === 'Keep', 'other columns preserved');
      let mapped = false;
      frappe.ui.Dialog = class {constructor() {mapped = true; throw Error('mapping opened');}};
      const ignoreMapping = event => {if (event.message.includes('mapping opened')) event.preventDefault();};
      window.addEventListener('error', ignoreMapping);
      paste('30\t40\n50\t60');
      window.removeEventListener('error', ignoreMapping);
      assert(mapped && rows[1].width === 10, 'multiple columns open mapping without changing cells');
      root.remove();
    }""")
    page.evaluate("""() => {
      window.materialHandlers = {};
      frappe.ui.form.on = (type, events) => Object.assign(materialHandlers[type] ||= {}, events);
      window.locals = {'Part List Materials': {row1: {parentfield: 'panel_materials'}}};
      window.$ = html => wrap([document.createElement('button')]);
      window.wrap = nodes => ({
        length: nodes.length,
        find(selector) {return wrap(nodes.flatMap(n => [...n.querySelectorAll(selector)]));},
        remove() {nodes.forEach(n => n.remove());return this;},
        is() {return true;},
        off() {return this;},
        on(type, fn) {nodes.forEach(n => n.addEventListener(type.split('.')[0], fn));return this;},
        attr(key, value) {nodes.forEach(n => n.setAttribute(key, value));return this;},
        text(value) {nodes.forEach(n => n.textContent = value);return this;},
        appendTo(target) {target.append(nodes);return this;},
        append(children) {children.forEach(n => nodes[0].append(n));}
      });
    }""")
    page.add_script_tag(path=str(Path(__file__).resolve().parents[1] / "c4factory/c4factory/doctype/part_list/part_list.js"))
    page.evaluate("""() => {
      const names = ['part_name','part_name_ar','lenght','width','hight','thickness','qty','material','note','edite_color','basic_color'];
      const assert = (ok, message) => {if (!ok) throw Error(message);};
      const root = document.createElement('div');
      root.innerHTML = '<div class="grid-body"><div class="grid-row">old cells</div></div>';
      const grid = {docfields: names.map(fieldname => ({fieldname})),
        visible_columns: [[{fieldname: 'material'}, 1]],
        user_defined_columns: [{fieldname: 'material'}],
        grid_rows: [{}], wrapper: wrap([root]), refresh() {this.refreshes = (this.refreshes || 0)+1;}};
      const frm = {doc: {doctype: 'Part List'}, fields_dict: {panel_materials: {grid}}};
      configurePartListMaterialColumns(frm);
      assert(JSON.stringify(grid.visible_columns.map(([df]) => df.fieldname)) === JSON.stringify(names), 'visible order');
      assert(JSON.stringify(grid.user_defined_columns.map(df => df.fieldname)) === JSON.stringify(names), 'saved definitions synchronized');
      assert(grid.grid_rows.length === 0 && !root.querySelector('.grid-row'), 'cached cells removed');
      configurePartListMaterialColumns(frm);
      assert(grid.refreshes === 1, 'unchanged refresh preserves editor');
      const form = document.createElement('div');
      form.innerHTML = '<button class="grid-collapse-row"></button><div class="grid-footer-toolbar"></div>';
      const row = {grid_form: {wrapper: wrap([form])}, toggle_view(show) {this.closed = show === false;}};
      grid.grid_rows_by_docname.row1 = row;
      materialHandlers['Part List Materials'].form_render(frm, 'Part List Materials', 'row1');
      assert(form.querySelector('.grid-footer-toolbar button').textContent === 'Done', 'Done button');
      form.querySelector('.grid-footer-toolbar button').click();
      assert(row.closed, 'Done closes editor');
      row.closed = false;
      form.querySelector('.grid-collapse-row').click();
      assert(row.closed, 'collapse closes editor');
    }""")
    browser.close()
print("PASS: column paste, rectangular paste, validation, row extension, and draft guard")
print("PASS: grid order, saved definitions, cached cells, and row editor close buttons")
