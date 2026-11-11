const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const handlers = [];
const preferences = {};
const wrapper = new Proxy({length: 0}, {get(target, key) {
  if (key in target) return target[key];
  return () => wrapper;
}});
const context = vm.createContext({
  __: value => value, $: () => wrapper,
  document: {getElementById: () => true},
  configurePartListMaterialColumns() {},
  frappe: {
    ui: {form: {on(type, events) {assert.equal(type, 'Part List'); handlers.push(events);}}},
    get_user_settings: (type, key) => preferences[key],
    model: {no_value_type: ['Section Break', 'HTML'], user_settings: Object.assign({}, {
      async save(type, key, value) {preferences[key] = value; return {message: preferences};},
    })},
  },
});
for (const file of ['part_list_columns.js', 'part_list_table_fullscreen.js']) {
  vm.runInContext(fs.readFileSync(`c4factory/public/js/doctype/${file}`, 'utf8'), context);
}
function grid(fieldname) {
  return {
    df: {fieldname}, doctype: 'Part List Materials',
    docfields: [
      {fieldname: 'material', fieldtype: 'Link', in_list_view: 1, columns: 2},
      {fieldname: 'qty', fieldtype: 'Float', in_list_view: 1, columns: 1},
      {fieldname: 'secret', fieldtype: 'Data', hidden: 1, columns: 2},
    ],
    reset_grid() {this.setup_visible_columns();},
    make_head() {},
  };
}
(async () => {
  const panel = grid('panel_materials');
  const metal = grid('metal_material');
  const frm = {doctype: 'Part List', doc: {docstatus: 1}, get_perm: () => true,
    fields_dict: {panel: {grid: panel}, metal: {grid: metal}}};
  const before = JSON.stringify(frm.doc);
  handlers[0].refresh(frm);
  assert.deepEqual(Array.from(panel.visible_columns, ([df]) => df.fieldname), ['material', 'qty']);
  preferences.C4TableColumns = {panel_materials: [
    {fieldname: 'qty', columns: 8}, {fieldname: 'material', columns: 7},
    {fieldname: 'secret', columns: 1}, {fieldname: 'removed', columns: 1},
  ]};
  panel.setup_visible_columns();
  assert.equal(panel.visible_columns.reduce((sum, [, width]) => sum + width, 0), 15,
    'Extended columns can exceed the native ten-column limit');
  assert.deepEqual(Array.from(panel.visible_columns, ([df]) => df.fieldname), ['qty', 'material']);
  assert.deepEqual(Array.from(metal.visible_columns, ([df]) => df.fieldname), ['material', 'qty'],
    'Material tables retain separate preferences despite sharing a child DocType');
  const setup = panel.setup_visible_columns;
  handlers[0].refresh(frm);
  assert.equal(panel.setup_visible_columns, setup, 'Repeated refresh does not wrap methods again');
  assert.equal(JSON.stringify(frm.doc), before, 'Display preferences do not change document data');
  assert.equal(panel.cannot_add_rows, undefined, 'Native row permissions are preserved');
  assert.doesNotThrow(() => handlers[1].onload(frm), 'Early full-screen setup tolerates missing wrappers');
  console.log('PASS: extended columns, isolated preferences, hidden fields, refresh stability, and native permissions');
})().catch(error => {console.error(error); process.exitCode = 1;});
