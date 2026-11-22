const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const script = fs.readFileSync('c4factory/public/js/doctype/project.js', 'utf8');
const handlers = {};
let registrations = 0;
let response;
const calls = [];
const context = vm.createContext({
  __: value => value,
  flt: value => Number(value || 0),
  locals: {},
  frappe: {
    ui: {form: {on(type, events) {registrations++; handlers[type] = events;}}},
    async call(args) {calls.push(args); return {message: response};},
  },
});
vm.runInContext(script, context);
vm.runInContext(script, context);
assert.equal(registrations, 2, 'global asset and doctype script must register each handler once');

const buttons = new Map();
const grid = {df: {}, get_selected_children() {return [];}};
const frm = {
  doc: {name: 'P-OLD'},
  fields_dict: {custom_project_boq: {grid}},
  is_new: () => false,
  is_dirty: () => false,
  add_custom_button(label, action) {buttons.set(label, action);},
  remove_custom_button(label) {buttons.delete(label);},
  refresh_field() {},
  set_df_property() {},
  dirty() {throw new Error('loading BOQ must not dirty Project');},
};

(async () => {
  response = {
    sales_order: 'SO-OLD', active: true,
    rows: [{sales_order_item: 'ROW-1', item_code: 'ITEM', actual_qty: 5,
      delivered_qty: 2, pds_status: 'PDS Request: REQ', installation_status: 'Pending Installation'}],
  };
  await handlers.Project.refresh(frm);
  assert.equal(calls[0].method, 'c4factory.api.project_boq.get_project_boq');
  assert.equal(frm.doc.sales_order, 'SO-OLD', 'missing forward link must not prevent loading');
  assert.equal(frm.doc.custom_project_boq.length, 1);
  assert.equal(frm.doc.custom_project_boq[0].item_code, 'ITEM');
  assert.equal(frm.doc.custom_project_boq[0].pds_status, 'PDS Request: REQ');
  assert.equal(frm.doc.custom_project_boq[0].delivered_qty, 2);
  assert.equal(grid.df.cannot_add_rows, true);
  assert.equal(grid.df.cannot_delete_rows, true);
  assert.ok(context.locals['Project BOQ Item'][frm.doc.custom_project_boq[0].name]);
  assert.ok(buttons.has('Create Delivery Note'));

  response = {sales_order: 'SO-OLD', active: false, rows: []};
  await buttons.get('Refresh BOQ')();
  assert.equal(frm.doc.custom_project_boq.length, 0, 'refresh must replace old rows');
  assert.ok(!buttons.has('Create Delivery Note'));

  delete frm.doc.sales_order;
  response = {sales_order: null, active: false, rows: []};
  await handlers.Project.refresh(frm);
  assert.equal(frm.doc.custom_project_boq.length, 0);
  assert.ok(!buttons.has('Create Delivery Note'));
  console.log('PASS: Project BOQ loads items and statuses, supports older links, and registers once');
})().catch(error => {console.error(error); process.exitCode = 1;});
