"""Exercise section defaults and atomic import rules in a real JS runtime."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        page.evaluate("""() => {
          window.__ = text => text;
          window.module = {exports: {}};
          window.handlers = {};
          window.locals = {};
          window.frappe = {
            ui: {form: {on(type, events) {Object.assign(handlers[type] ||= {}, events);}}},
            utils: {escape_html: text => text},
            db: {async get_value(type, name) {
              return {message: type === 'Part Material' ? {color_palette: 'Wood'} :
                {palette: name === 'Chrome' ? 'Metal' : 'Wood', disable: name === 'Retired' ? 1 : 0}};
            }},
          };
        }""")
        for name in ("part_list_import.js", "part_list_material_colors.js"):
            page.add_script_tag(path=str(ROOT / "c4factory/public/js/doctype" / name))
        page.evaluate("""async () => {
          const assert = (ok, message) => {if (!ok) throw Error(message);};
          const frm = {doc: {doctype:'Part List', docstatus:0, panel_materials:[], metal_material:[]},
            refresh_field() {}, dirty() {}, clear_table(table) {this.doc[table] = [];},
            add_child(table, value) {(this.doc[table] ||= []).push(value);}, set_query() {}};
          const batch = color => [{table:'panel_materials', rows:[{values:{material:'MDF',
            part_name:'Top', qty:1, basic_color:color}}]}];
          const apply = module.exports.applyImportBatches;
          await apply(frm, batch('Oak'), 'Add Rows');
          assert(frm.doc.panel_base_color === 'Oak' && frm.doc.panel_color_palette === 'Wood', 'Import fills header');
          assert(frm.doc.panel_materials[0].basic_color === 'Oak', 'Import fills row');
          await apply(frm, batch('Oak'), 'Add Rows');
          assert(frm.doc.panel_materials.length === 2, 'Matching append allowed');
          for (const [color, mode] of [['Walnut','Add Rows'],['Retired','Replace Table Rows'],['Chrome','Replace Table Rows']]) {
            const before = JSON.stringify(frm.doc);
            let rejected = false;
            try {await apply(frm, batch(color), mode);} catch {rejected = true;}
            assert(rejected && JSON.stringify(frm.doc) === before, 'Invalid import is atomic: ' + color);
          }
          frm.doc.panel_base_color = 'Walnut';
          handlers['Part List'].panel_base_color(frm);
          assert(frm.doc.panel_materials.every(row => row.basic_color === 'Walnut'), 'Header updates all rows');
          frm.doc.metal_material = [{basic_color:'Chrome', color_palette:'Metal'}];
          frm.doc.panel_color_palette = 'Metal';
          await handlers['Part List'].panel_color_palette(frm);
          assert(frm.doc.panel_base_color === null, 'Palette clears base');
          assert(frm.doc.panel_materials.every(row => row.basic_color === null && row.color_palette === 'Metal'), 'Palette clears incompatible rows');
          assert(frm.doc.metal_material[0].basic_color === 'Chrome', 'Other sections unchanged');
          frm.doc.docstatus = 1;
          frm.doc.panel_base_color = 'Chrome';
          handlers['Part List'].panel_base_color(frm);
          assert(frm.doc.panel_materials[0].basic_color === null, 'Submitted rows unchanged');
          frm.doc.docstatus = 0;
          frm._applyingPartListCopy = true;
          handlers['Part List'].panel_base_color(frm);
          assert(frm.doc.panel_materials[0].basic_color === null, 'Copies preserve individual colors');
        }""")
        browser.close()
    print("Browser passed: header defaults, matching append, atomic rejection, palette changes, section isolation, submitted/copy guards.")


if __name__ == "__main__":
    main()
