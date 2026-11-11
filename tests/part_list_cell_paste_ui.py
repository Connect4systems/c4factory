"""Run with python tests/part_list_cell_paste_ui.py."""
from pathlib import Path

from playwright.sync_api import sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page()
    page.evaluate("""() => {
      window.__ = (text, args=[]) => text.replace(/\{(\d+)\}/g, (_, n) => args[n]);
      window.module = {exports: {}};
      window.frappe = {utils: {escape_html: String}, ui: {form: {on() {}}}};
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
    browser.close()
print("PASS: column paste, rectangular paste, validation, row extension, and draft guard")
