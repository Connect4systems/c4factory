const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = {};
let writes = 0;
let lookups = 0;
const row = {doctype: 'Part List Materials', name: 'row1', parentfield: 'panel_materials', material: 'MDF', color_doctype: '', basic_color: ''};
const frm = {
  doc: {doctype: 'Part List', docstatus: 0, product: 'CUBE', product_image: 'image.png', material_line: 'LINE-1', metal_material_line: 'LINE-1', panel_materials: [row]},
  refresh_field() {}, add_custom_button() {},
  async set_value(field, value) {writes++; this.doc[field] = value;},
};
const context = vm.createContext({
  __: x => x, locals: {'Part List Materials': {row1: row}},
  frappe: {
    ui: {form: {on(type, events) {(handlers[type] ||= []).push(events);}}},
    utils: {escape_html: x => x},
    db: {async get_value(type) {lookups++; return {message: type === 'Item' ? {image: 'new.png'} : {color: 'P-Natural'}};}},
    model: {async set_value(type, name, field, value) {writes++; Object.assign(row, typeof field === 'object' ? field : {[field]: value});}},
  },
});
for (const path of ['c4factory/c4factory/doctype/part_list/part_list.js', 'c4factory/public/js/doctype/part_list_material_colors.js']) {
  vm.runInContext(fs.readFileSync(path, 'utf8'), context);
}
(async () => {
  for (const status of [0, 1]) {
    frm.doc.docstatus = status;
    const before = JSON.stringify(frm.doc);
    for (let i = 0; i < 3; i++) for (const events of handlers['Part List']) await events.refresh?.(frm);
    assert.equal(JSON.stringify(frm.doc), before, 'Refresh must leave all saved document data unchanged');
  }
  assert.equal(writes, 0);
  assert.equal(lookups, 0, 'Refresh must not start asynchronous data updates after save');
  await handlers['Part List Materials'][0].material(frm, row.doctype, row.name);
  assert.equal(row.color_doctype, 'P-Natural', 'Panels must use the selected Part Material color type');
  assert.ok(writes > 0, 'User edits must still update row values');
  await handlers['Part List'][0].product(frm);
  assert.equal(frm.doc.product_image, 'new.png');
  const meta = JSON.parse(fs.readFileSync('c4factory/c4factory/doctype/part_list/part_list.json', 'utf8'));
  assert.equal(meta.is_submittable, 1);
  for (const name of ['wood_type', 'wood_color', 'wood_color_doctype', 'metal_color']) assert.ok(!meta.fields.some(f => f.fieldname === name));
  for (const name of ['material_line', 'metal_material_line']) {
    const field = meta.fields.find(f => f.fieldname === name);
    assert.equal(field.fetch_from, 'product.custom_material_line');
    assert.equal(field.options, 'Material Line');
    assert.equal(field.read_only, 1);
  }
  console.log('PASS: draft/submitted refresh preserves data, no async refresh writes, material colors, product image, and field schema');
})().catch(error => {console.error(error); process.exitCode = 1;});
