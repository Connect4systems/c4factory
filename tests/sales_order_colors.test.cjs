const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = {};
const writes = [];
const item = {name: 'ROW', custom_part_list: 'PL'};
const context = vm.createContext({
  __: value => value,
  locals: {'Sales Order Item': {ROW: item}},
  frappe: {
    ui: {form: {on(type, events) {handlers[type] = events;}}},
    utils: {escape_html: value => value},
    async call() {return {message: {
      wood_color: 'Legacy Wood', metal_color: 'Legacy Metal', wood_color_doctype: 'P-Wood',
      rows: [{source_row: 'M', color_doctype: 'P-Natural', color: 'Oak', edite_color: 1}],
    }};},
    model: {async set_value(type, name, values) {writes.push(values); Object.assign(item, values);}},
  },
});
vm.runInContext(fs.readFileSync('c4factory/public/js/doctype/sales_order/item_colors.js', 'utf8'), context);
const frm = {doc: {docstatus: 0}, fields_dict: {}};
(async () => {
  assert.ok(!handlers['Sales Order Item'].custom_wood);
  assert.ok(!handlers['Sales Order Item'].custom_metal);
  await handlers['Sales Order Item'].custom_part_list(frm, 'Sales Order Item', 'ROW');
  let data = JSON.parse(item.custom_color_sample_data);
  assert.equal(data.rows[0].color, 'Oak');
  data.rows[0].color = 'Walnut';
  item.custom_color_sample_data = JSON.stringify(data);
  await handlers['Sales Order Item'].form_render(frm, 'Sales Order Item', 'ROW');
  assert.equal(JSON.parse(item.custom_color_sample_data).rows[0].color, 'Walnut');
  item.custom_part_list = null;
  await handlers['Sales Order Item'].custom_part_list(frm, 'Sales Order Item', 'ROW');
  assert.equal(item.custom_color_sample_data, null);
  context.locals['Color Sample Item'] = {ROW: item};
  item.custom_part_list = 'PL';
  await handlers['Color Sample Item'].custom_part_list(frm, 'Color Sample Item', 'ROW');
  assert.equal(JSON.parse(item.custom_color_sample_data).rows[0].color, 'Oak');
  const sampleMeta = JSON.parse(fs.readFileSync('c4factory/c4factory/doctype/color_sample_item/color_sample_item.json', 'utf8'));
  for (const name of ['custom_wood', 'custom_metal', 'custom_wood_color_doctype']) {
    assert.ok(!sampleMeta.fields.some(field => field.fieldname === name));
    assert.ok(!sampleMeta.field_order.includes(name));
  }
  for (const values of writes) {
    for (const name of ['custom_wood', 'custom_metal', 'custom_wood_color_doctype']) assert.ok(!(name in values));
  }
  assert.ok(!handlers['Color Sample Item'].custom_wood);
  assert.ok(!handlers['Color Sample Item'].custom_metal);
  console.log('PASS: Sales Order and Color Sample row colors work without header fields or handlers');
})().catch(error => {console.error(error); process.exitCode = 1;});
