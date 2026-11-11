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
    reset_grid() {this.make_head(); this.setup_visible_columns();},
    make_head() {
      this.header_row = {
        validate_columns_width() {throw new Error('The total column width cannot be more than 10.');},
        prepare_columns_for_dialog() {return [];},
        configure_dialog_for_columns_selector() {
          this.grid_settings_dialog = {
            set_primary_action(label, callback) {this.primary = callback;},
            set_secondary_action(callback) {this.secondary = callback;},
            hide() {this.hidden = true;},
          };
        },
      };
    },
  };
}
(async () => {
  const panel = grid('panel_materials');
  const metal = grid('metal_material');
  const frm = {doctype: 'Part List', doc: {docstatus: 1}, get_perm: () => true,
    fields_dict: {panel: {grid: panel}, metal: {grid: metal}}};
  const before = JSON.stringify(frm.doc);
  handlers[0].refresh(frm);
  assert.deepEqual(Array.from(panel.visible_columns, ([df]) => df.fieldname), ['qty', 'material']);
  preferences.C4TableColumns = {panel_materials: [
    {fieldname: 'qty', columns: 8}, {fieldname: 'material', columns: 7},
    {fieldname: 'secret', columns: 1}, {fieldname: 'removed', columns: 1},
  ]};
  panel.setup_visible_columns();
  assert.equal(panel.visible_columns.reduce((sum, [, width]) => sum + width, 0), 15,
    'Extended columns can exceed the native ten-column limit');
  assert.deepEqual(Array.from(panel.visible_columns, ([df]) => df.fieldname), ['qty', 'material']);
  assert.deepEqual(Array.from(metal.visible_columns, ([df]) => df.fieldname), ['qty', 'material'],
    'Material tables retain separate preferences despite sharing a child DocType');
  const header = panel.header_row;
  header.selected_columns_for_grid = [{fieldname: 'qty', columns: 8}, {fieldname: 'material', columns: 7}];
  header.configure_dialog_for_columns_selector();
  const dialog = header.grid_settings_dialog;
  await dialog.primary();
  assert.equal(dialog.hidden, true, 'Update saves and closes the actual column picker above ten units');
  assert.equal(preferences.C4TableColumns.panel_materials.length, 2);
  assert.equal(panel.visible_columns.reduce((sum, [, width]) => sum + width, 0), 15);
  assert.equal(preferences.C4TableColumns.metal_material, undefined);
  const setup = panel.setup_visible_columns;
  handlers[0].refresh(frm);
  assert.equal(panel.setup_visible_columns, setup, 'Repeated refresh does not wrap methods again');
  assert.equal(JSON.stringify(frm.doc), before, 'Display preferences do not change document data');
  assert.equal(panel.cannot_add_rows, undefined, 'Native row permissions are preserved');
  assert.doesNotThrow(() => handlers[1].onload(frm), 'Early full-screen setup tolerates missing wrappers');
  console.log('PASS: extended columns, isolated preferences, hidden fields, refresh stability, and native permissions');
})().catch(error => {console.error(error); process.exitCode = 1;});
