"""Headless browser smoke test with a small Frappe adapter and the real preview parser.

Run: python tests/part_list_import_ui.py
Optional: --workbook PATH (repeat for customer workbook regression checks).
This exercises client dialogs, not a deployed Frappe site.
"""
import argparse
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from test_part_list_save import ROOT, load_module


ADAPTER = r"""() => {
window.__ = (text, values=[]) => text.replace(/\{(\d+)\}/g, (_, n) => values[n]);
window.module = {exports:{}};
window.handlers = {}; window.dialogs = []; window.alerts = []; window.calls = [];
function wrap(element) { return {
  find: selector => [...element.querySelectorAll(selector)],
  prop(name, value) {element[name] = value; return this;}
}; }
window.frappe = {
  utils: {escape_html(value) {const el=document.createElement('span');el.textContent=value;return el.innerHTML;}},
  ui: {form: {on(type, events) {handlers[type] = events;}}},
  user_roles: ['Technical'],
  msgprint(message) { alerts.push(message); }, show_alert(message) {alerts.push(message);},
  db: {async get_value() {if(window.failLookup) throw Error('Lookup failed');return {message:{color_palette:'Wood'}};}},
  async call(request) {
    calls.push(request);
    if(request.method.endsWith('preview_import')) return {message:await previewServer(request.args)};
    if(request.method.endsWith('inspect_workbook')) return {message:window.testWorkbook};
    if(request.method.endsWith('map_accessories')) return {message:{matched:1,total:1}};
    throw Error('Unexpected API: '+request.method);
  }
};
frappe.ui.Dialog = class {
  constructor(options) {
    this.options=options;this.fields_dict={};dialogs.push(this);
    this.element=document.createElement('div');this.element.className='dialog';document.body.append(this.element);
    const heading=document.createElement('h3');heading.textContent=options.title;this.element.append(heading);
    for(const f of options.fields) {
      const field={df:f}; const area=document.createElement('div');this.element.append(area);field.$wrapper=wrap(area);field.area=area;
      if(f.hidden)area.hidden=true;
      if(f.fieldtype==='HTML') area.innerHTML=f.options||'';
      else if(f.fieldtype==='Section Break') {const h=document.createElement('h4');h.textContent=f.label;area.append(h);}
      else {
        const label=document.createElement('label');label.textContent=f.label||'';area.append(label);
        const input=document.createElement(f.fieldtype==='Select'?'select':f.fieldtype==='Small Text'?'textarea':f.fieldtype==='Button'?'button':'input');
        if(f.fieldtype==='Select') for(const v of (f.options||'').split('\n')) {const option=document.createElement('option');option.value=v;option.textContent=v;input.append(option);}
        input.value=f.default??'';input.dataset.field=f.fieldname;area.append(input);field.input=input;
        input.addEventListener('change',()=>f.onchange?.());
        if(f.fieldtype==='Button') {input.textContent=f.label;input.addEventListener('click',()=>f.click?.());}
      }
      if(f.fieldname)this.fields_dict[f.fieldname]=field;
    }
    this.primary=document.createElement('button');this.primary.textContent=options.primary_action_label;this.primary.dataset.primary='1';
    this.primary.onclick=async()=>{try {await options.primary_action(this.get_values());} catch(e) {window.lastError=e.message;}};
    this.element.append(this.primary);
  }
  get_values() {return Object.fromEntries(Object.entries(this.fields_dict).filter(([k,f])=>f.input).map(([k,f])=>[k,f.input.value]));}
  get_value(key) {return this.fields_dict[key].input.value;}
  async set_value(key,value) {const f=this.fields_dict[key];f.input.value=value;await f.df.onchange?.();}
  set_df_property(key, property, value) {
    const field=this.fields_dict[key];field.df[property]=value;
    if(property==='hidden')field.area.hidden=Boolean(value);
    if(property==='options') {field.input.innerHTML='';for(const v of value.split('\n')) {const option=document.createElement('option');option.value=v;option.textContent=v;field.input.append(option);}}
  }
  get_primary_btn() {return wrap(this.primary);}
  show() {this.element.hidden=false;}
  hide() {this.element.hidden=true;}
};
frappe.ui.FileUploader = class {constructor(options){window.uploadOptions=options;}};
window.frm = {
  doc:{name:'PL',modified:'STAMP',docstatus:0,panel_materials:[],metal_material:[],other_material:[],accessorise_table:[]},
  dashboard:{add_indicator(){}},buttons:{},
  add_custom_button(label, callback) {this.buttons[label]=callback;},
  add_child(table, values) {const row={...values};this.doc[table].push(row);return row;},
  clear_table(table) {this.doc[table]=[];},refresh_field(){},dirty(){this.changed=true;},async reload_doc(){this.reloaded=true;}
};
}"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workbook', action='append', default=[])
    args = parser.parse_args()
    frappe = ModuleType('frappe')
    frappe.whitelist = lambda: lambda fn: fn
    frappe._ = lambda text: text
    with patch.dict(sys.modules, {'frappe': frappe}):
        api = load_module('c4factory/api/part_list_import.py', 'browser_import_test')

    # Read the exact customer files when explicitly supplied, without committing data.
    for path in args.workbook:
        sheets = api.read_workbook(Path(path).read_bytes(), path)
        data = sheets['Part L.']
        sections = [('panel_materials', ['panel', 'wooden panel']), ('metal_material', ['metal']), ('accessorise_table', ['accessories'])]
        counts = {}
        for table, markers in sections:
            index = next(i for i, r in enumerate(data) if str(r[0]).strip().lower() in markers)
            accessory = table == 'accessorise_table'
            start = index + (3 if accessory else 2)
            end = next((i for i, r in enumerate(data) if i >= start - 1 and str(r[0]).strip().lower() in ['metal', 'accessories', 'drawn by']), len(data))
            mapping = {'requested_name':2, 'qty':10, 'note':6} if accessory else {'part_name':2, 'part_name_ar':3, 'lenght':6, 'width':7, 'hight':8, 'thickness':9, 'qty':10}
            preview = api.build_preview(data, mapping, table, 'Selected material', start, end)
            assert all(not r['errors'] for r in preview), preview
            counts[table] = len(preview)
        print(f'{Path(path).name}: {json.dumps(counts)}')

    def preview_server(args):
        return api.build_preview(json.loads(args['matrix']), json.loads(args['mapping']), args['table'], args['material'], args['start_row'], args['end_row'])

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page()
        page.set_content('<h2>Part List import test</h2>')
        # about:blank has no localStorage; importing still works via the optional-storage fallback.
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.expose_function('previewServer', preview_server)
        page.evaluate(ADAPTER)
        page.add_script_tag(path=str(ROOT / 'c4factory/public/js/doctype/part_list_import.js'))
        assert page.evaluate("module.exports.column(26)") == 'AA'
        assert page.evaluate('module.exports.parsePaste(' + json.dumps('"Long\nScrew"\t8\r\n') + ')') == [['Long\nScrew', '8']]
        page.evaluate("handlers['Part List'].refresh(frm);frm.buttons['Panel Materials']()")
        page.locator('[data-field=paste]').fill('Top\tقرصة\t1200\t800\t\t25\t3\nDrawer Unit\tوحدة أدراج\t428\t700\t627\t\t1')
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.locator('[data-field=default_material]').fill('MDF')
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.wait_for_function('dialogs.length === 3')
        assert page.locator('.dialog').last.locator('input:checked').count() == 1, 'Assembly should require explicit inclusion'
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.wait_for_function('frm.doc.panel_materials.length === 1')
        part = page.evaluate('frm.doc.panel_materials[0]')
        assert part['part_name_ar'] == 'قرصة' and part['thickness'] == 25 and part['hight'] is None
        assert part['color_palette'] == 'Wood'
        # A failed material lookup must leave the old table intact in Replace mode.
        page.evaluate("frm.buttons['Panel Materials']()")
        page.locator('.dialog').last.locator('[data-field=paste]').fill('Bottom\tقاعدة\t100\t80\t\t18\t2')
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.locator('.dialog').last.locator('[data-field=default_material]').fill('MDF')
        page.locator('.dialog').last.locator('[data-field=mode]').select_option('Replace Table Rows')
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.wait_for_function('dialogs.length === 6')
        page.evaluate('window.failLookup=true')
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.wait_for_function("window.lastError === 'Lookup failed'")
        assert page.evaluate('frm.doc.panel_materials[0].part_name') == 'Top'
        page.evaluate('window.failLookup=false;window.lastError=null')
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.wait_for_function("frm.doc.panel_materials[0].part_name === 'Bottom'")
        assert page.evaluate('frm.doc.panel_materials.length') == 1
        page.evaluate("frm.buttons['Accessories']()")
        page.locator('.dialog').last.locator('[data-field=paste]').fill('"Screw\nlong"\t8\nNut\t-1')
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.wait_for_function('dialogs.length === 9')
        assert page.locator('.dialog').last.locator('input:disabled').count() == 1
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.wait_for_function('frm.doc.accessorise_table.length === 1')
        assert page.evaluate('frm.doc.accessorise_table[0].requested_name') == 'Screw\nlong'
        page.evaluate("frm.doc.docstatus=1;frm.doc.accessorise_table[0].name='ACC';frappe.user_roles=['Stock User'];handlers['Part List'].refresh(frm);frm.buttons['Map Accessories']()")
        page.locator('[data-field=item_0]').fill('SCREW')
        page.locator('[data-field=uom_0]').fill('Box')
        page.locator('[data-field=factor_0]').fill('10')
        page.locator('.dialog').last.locator('[data-primary]').click()
        page.wait_for_function('frm.reloaded === true')
        mappings = json.loads(page.evaluate('calls[calls.length-1].args.mappings'))
        assert mappings == [{'row':'ACC', 'item':'SCREW', 'requested_uom':'Box', 'conversion_factor':'10'}]
        # A source sheet's name and the originally clicked table do not determine
        # the import: the user selects a section header and its destination.
        worksheet = [
            ['SN', 'Code', 'Materials', '', '', 'U.O.M', 'Dim.', '', '', '', 'Qty.'],
            ['Wooden Panel'],
            [1, '', 'Top', 'القرصة', '', 'Sheet', 1200, 1200, '', 25, 3],
            ['Metal'],
            [1, '', 'Leg', 'رجل', '', 'Unit', 1200, 48, 715, 1.8, 2],
            ['Other'],
            [1, '', 'Foam', 'فوم', '', 'Unit', 10, 20, '', 5, 1],
            ['Accessories'],
            ['', 'Code', 'Items', 'Supplier', '', '', 'Notes', '', '', '', 'Qty.'],
            [1, '', 'Screw', '', '', '', '', '', '', '', 8],
            ['Drawn By'],
        ]
        page.evaluate('window.testWorkbook=' + json.dumps({'Customer layout': worksheet}))
        detected = page.evaluate('module.exports.detectSections(testWorkbook["Customer layout"])')
        assert [s['table'] for s in detected] == ['panel_materials', 'metal_material', 'other_material', 'accessorise_table']
        for label in ['Material', 'Materials', 'Wooden Panel', 'Woodin Panel', 'Panel']:
            assert page.evaluate('module.exports.sectionType(' + json.dumps(label) + ')') == 'panel_materials'
        for header, target, material, expected_row in [
            ('2: Wooden Panel', 'Panel Materials', 'MDF', 3),
            ('4: Metal', 'Metal Material', 'Steel', 5),
            ('6: Other', 'Other Material', 'Foam', 7),
            ('8: Accessories', 'Accessories', '', 10),
        ]:
            page.evaluate("frm.doc.docstatus=0;handlers['Part List'].refresh(frm);frm.buttons['Panel Materials']()")
            page.locator('.dialog').last.locator('[data-field=upload]').click()
            page.evaluate("async()=>await uploadOptions.on_success({file_url:'/private/files/test.xls'})")
            page.locator('.dialog').last.locator('[data-primary]').click()
            chooser = page.locator('.dialog').last
            chooser.locator('[data-field=source_section]').select_option(header)
            assert chooser.locator('[data-field=target_table]').input_value() == target
            # Explicitly override the destination for Other to prove it is selectable.
            if header == '6: Other':
                chooser.locator('[data-field=target_table]').select_option('Panel Materials')
            if material and header != '2: Wooden Panel':
                chooser.locator('[data-field=section_material]').fill(material)
            chooser.locator('[data-primary]').click()
            config = page.locator('.dialog').nth(page.locator('.dialog').count() - 1)
            assert config.locator('[data-field=start]').input_value() == str(expected_row)
            assert config.locator('[data-field=end]').input_value() == str(expected_row)
            if header == '2: Wooden Panel':
                before = page.evaluate('dialogs.length')
                config.locator('[data-primary]').click()
                assert page.evaluate('dialogs.length') == before, 'Missing material must be resolved before review'
                assert 'Choose a Part Material' in page.evaluate('alerts[alerts.length-1]')
                config.locator('[data-field=default_material]').fill(material)
            if material:
                assert config.locator('[data-field=default_material]').input_value() == material
            config.locator('[data-primary]').click()
            page.wait_for_function("dialogs[dialogs.length-1].options.title.startsWith('Review Import:')")
            review = page.locator('.dialog').last
            if header == '2: Wooden Panel':
                review.locator('[data-field=back_to_mapping]').click()
                assert config.is_visible()
                assert config.locator('[data-field=default_material]').input_value() == material
                config.locator('[data-primary]').click()
                page.wait_for_function("dialogs[dialogs.length-1].options.title.startsWith('Review Import:')")
                review = page.locator('.dialog').last
            assert review.locator('input:checked').count() == 1
            assert review.locator('input:disabled').count() == 0
            review.locator('[data-field=deselect_all]').click()
            assert review.locator('input:checked').count() == 0
            review.locator('tbody tr td').nth(1).click()
            assert review.locator('input:checked').count() == 1, 'Clicking the row must select it'
            review.locator('input[type=checkbox]').uncheck()
            review.locator('[data-field=select_all]').click()
            assert review.locator('input:checked').count() == 1
            review.locator('[data-primary]').click()
            page.wait_for_function('dialogs[dialogs.length-1].element.hidden === true')
        assert page.evaluate('frm.doc.panel_materials.length') == 3
        assert page.evaluate('frm.doc.panel_materials[2].part_name') == 'Foam'
        assert page.evaluate('frm.doc.metal_material.length') == 1
        assert page.evaluate('frm.doc.metal_material[0].hight') == 715
        assert page.evaluate('frm.doc.metal_material[0].thickness') == 1.8
        assert page.evaluate('frm.doc.accessorise_table.length') == 2
        assert not errors, errors
        assert not page.evaluate('window.lastError'), page.evaluate('window.lastError')
        browser.close()
    print('Browser passed: paste/upload, section-header selection, destination override, vertical mapping, material requirement, checkbox/row/bulk selection, Arabic, dimensions, assemblies, invalid quantity, stock mapping.')


if __name__ == '__main__':
    main()
