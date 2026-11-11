const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let dialog;
const context = vm.createContext({
  __: text => text,
  frappe: {
    ui: {
      form: {on() {}},
      Dialog: class {
        constructor(config) { Object.assign(this, config); this.values = {}; dialog = this; }
        get_value(field) { return this.values[field]; }
        set_value(field, value) { this.values[field] = value; }
        show() {}
      },
    },
    utils: {escape_html: text => text},
  },
});
vm.runInContext(fs.readFileSync('c4factory/c4factory/doctype/part_list/part_list.js', 'utf8'), context);
vm.runInContext('openPartBundleSelector({})', context);
const group = dialog.fields.find(field => field.fieldname === 'bundle_group');
const bundle = dialog.fields.find(field => field.fieldname === 'part_bundle');
assert.equal(group.reqd, 1);
assert.equal(group.options, 'Bundle Group');
assert.equal(bundle.reqd, 1);
dialog.values.bundle_group = 'Doors';
assert.equal(bundle.get_query().filters.bundle_group, 'Doors');
dialog.values.part_bundle = 'Door bundle';
dialog.values.bundle_group = 'Cabinets';
group.onchange();
assert.equal(dialog.values.part_bundle, null);
assert.equal(bundle.get_query().filters.bundle_group, 'Cabinets');
console.log('PASS: required group filters bundles and changing group clears selection');
