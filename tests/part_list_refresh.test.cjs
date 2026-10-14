const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = {};
let writes = 0;
const row = { doctype: 'Part List Materials', name: 'row1', parentfield: 'panel_materials', material: 'MDF', color_doctype: '', basic_color: '' };
const frm = {
  doc: { doctype: 'Part List', docstatus: 0, product: 'CUBE', product_image: 'image.png', wood_type: 'Artificial Wood', wood_color_doctype: '', panel_materials: [row] },
  meta: { fields: [{fieldtype: 'Table', options: 'Part List Materials', fieldname: 'panel_materials'}] },
  fields_dict: { wood_color: {df: {fieldtype: 'Dynamic Link'}}, wood_color_doctype: {} },
  refresh_field() {}, set_df_property() {}, add_custom_button() {},
  async set_value(field, value) { writes++; this.doc[field] = value; },
};
const context = vm.createContext({
  __: x => x, locals: {'Part List Materials': {row1: row}},
  frappe: {
    ui: {form: {on(type, events) { (handlers[type] ||= []).push(events); }}},
    utils: {escape_html: x => x},
    db: {async get_value() {return {message: {image: 'image.png', color: null}};}},
    model: {async set_value(type, name, field, value) {writes++; row[field] = value;}},
  },
});
for (const path of ['c4factory/c4factory/doctype/part_list/part_list.js', 'c4factory/public/js/doctype/part_list_material_colors.js']) {
  vm.runInContext(fs.readFileSync(path, 'utf8'), context);
}
(async () => {
  for (let i = 0; i < 3; i++) {
    for (const events of handlers['Part List']) await events.refresh?.(frm);
  }
  assert.equal(writes, 0, 'Repeated saved-form refresh must not call document setters');
  assert.equal(row.color_doctype, 'P-Wood');
  assert.equal(frm.doc.wood_color_doctype, 'P-Wood');
  row.parentfield = 'other_material';
  row.color_doctype = '';
  await handlers['Part List Materials'][0].form_render(frm, row.doctype, row.name);
  assert.equal(writes, 0, 'Opening a child row without a color source must not dirty the form');
  frm.doc.wood_type = 'Natural Wood';
  await handlers['Part List'][0].wood_type(frm);
  assert.ok(writes > 0, 'User color edits must still use setters');
  assert.equal(frm.doc.wood_color_doctype, 'P-Natural');
  console.log('PASS: repeated refresh, child form rendering, and editable wood type');
})().catch(error => {console.error(error); process.exitCode = 1;});
