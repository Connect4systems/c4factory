"""Browser smoke test with a small Frappe adapter; requires Playwright and jQuery."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--jquery", required=True)
	parser.add_argument("--channel", default="msedge")
	parser.add_argument("--screenshot")
	args = parser.parse_args()
	meta = json.loads((ROOT / "c4factory/c4factory/doctype/part_list/part_list.json").read_text())
	with sync_playwright() as playwright:
		browser = playwright.chromium.launch(channel=args.channel, headless=True)
		page = browser.new_page(viewport={"width": 1440, "height": 1000})
		errors = []
		page.on("pageerror", lambda error: errors.append(str(error)))
		page.set_content("""<style>
body{font:14px Arial;background:#f3f5f7;color:#30343b} .dialog{background:white;margin:20px;padding:20px;border:1px solid #ddd;max-width:1320px}
table{border-collapse:collapse;width:100%}th,td{padding:10px;border:1px solid #ddd;text-align:left}button{cursor:pointer;margin:5px;padding:6px 12px}
.card{background:white;border:1px solid #ccc;border-radius:8px;box-shadow:0 8px 30px #0003}.card-header{background:#f0f1f4;padding:12px;display:flex;justify-content:space-between}.card-body{padding:18px}
.text-muted{color:#737a84}.dialog-columns{display:flex;gap:15px}.dialog-columns>div{width:50%}input,select{margin:5px;padding:8px}img{display:block;margin:auto}
</style><h2>Part List version and import smoke test</h2><div id='actions'></div>""")
		page.add_script_tag(path=args.jquery)
		page.evaluate("window.testMeta = " + json.dumps(meta))
		page.evaluate(r"""() => {
window.__ = text => text;
window.cint = value => parseInt(value || 0, 10);
window.flt = value => parseFloat(value || 0);
window.handlers = {};
window.sequence = 0;
window.testPayload = {source:'CUBE-01', values:{product:'CUBE', product_name:'Coffee Table', description:'Imported description',
  product_image:'data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220"><rect width="360" height="220" fill="#eee"/><path d="M50 55h260v30H50zm15 30h12v100H65zm220 0h12v100h-12z" fill="#878e97"/></svg>'),
  material_line:'Custom Material', metal_material_line:'Custom Material',width:60,hight:45,depth:60,
  is_default:1,disable:0,pds_table:[{title:'Drawing',arttach:'/private/files/design.pdf'}],
  panel_materials:[{material:'MDF',qty:3,basic_color:'Oak',color_doctype:'P-Wood'}],metal_material:[],other_material:[],accessorise_table:[]}};
window.frappe = {
  utils:{escape_html:text=>$('<div>').text(String(text??'')).html()},urllib:{get_full_url:url=>url},
  ui:{form:{on(type,events){handlers[type]=Object.assign(handlers[type]||{},events)}}},
  get_meta:()=>testMeta,
  model:{can_create:()=>true,async with_doctype(){},get_new_doc(){const doc={doctype:'Part List',name:'new-'+(++sequence),docstatus:0};window.newDraft=doc;return doc},
    add_child(doc,type,table){const row={doctype:type,name:'child-'+(++sequence)};(doc[table]||=[]).push(row);return row}},
  set_route(...route){window.lastRoute=route},show_alert(){},msgprint(message){throw Error(message)},confirm(message,yes){yes()},
  db:{async get_value(type){return {message:type==='Item Group'?{lft:1,rgt:4,is_group:1}:{image:'wrong.png',custom_material_line:'wrong-default'}}},async get_list(){return [{name:'Tables'}]}},
  async call(request){
    if(request.method.endsWith('get_copy_payload'))return {message:structuredClone(testPayload)};
    if(request.method.endsWith('get_selector_items'))return {message:{total:1,items:[{part_list_id:'CUBE-01',item_code:'CUBE',item_name:'Coffee Table',
      description:'Coffee table description',material_line:'Custom Material',image:testPayload.values.product_image,width:60,height:45,depth:60,item_group:'Tables',uom:'Nos'}]}};
    throw Error('Unexpected API '+request.method);
  },
};
frappe.ui.Dialog=class {
  constructor(options){
    this.options=options;this.fields_dict={};window.lastDialog=this;
    this.root=$('<div class="dialog">').appendTo('body');$('<h3>').text(options.title).appendTo(this.root);
    const filters=$('<div>').appendTo(this.root);const columns=$('<div class="dialog-columns">').appendTo(this.root);
    for(const field of options.fields){if(!field.fieldname)continue;
      const wrapper=$('<div>').appendTo(field.fieldtype==='HTML'?columns:filters);const entry={$wrapper:wrapper};
      if(field.fieldtype!=='HTML'){
        entry.$input=field.fieldtype==='Button'?$('<button>').text(field.label):field.fieldtype==='Select'?$('<select>'): $('<input>');
        if(field.options&&field.fieldtype==='Select')for(const value of field.options.split('\n'))$('<option>').text(value).val(value).appendTo(entry.$input);
        entry.$input.attr('data-field',field.fieldname).appendTo(wrapper);wrapper.css('display','inline-block');
        if(field.default)entry.$input.val(field.default);
      }this.fields_dict[field.fieldname]=entry;
    }
    this.button=$('<button data-primary>Import</button>').appendTo(this.root).on('click',()=>options.primary_action());
  }
  get_field(name){return this.fields_dict[name]}get_value(name){return this.fields_dict[name].$input.val()}
  async set_value(name,value){this.fields_dict[name].$input.val(value)}
  disable_primary_action(){this.button.prop('disabled',true)}enable_primary_action(){this.button.prop('disabled',false)}show(){}hide(){this.root.remove()}
};
window.makeForm=(status)=>({
  doc:{doctype:'Part List',name:'TARGET',docstatus:status,product:'OTHER',version_of:'ORIGINAL',pds_table:[{title:'Old'}],panel_materials:[]},
  meta:testMeta,fields_dict:{},buttons:{},is_new(){return false},
  add_custom_button(label,action){this.buttons[label]=action},refresh_field(){},refresh_fields(){},dirty(){this.doc.__unsaved=1},
  async set_value(values,value){if(typeof values==='string')values={[values]:value};Object.assign(this.doc,values);for(const key of Object.keys(values))await handlers['Part List']?.[key]?.(this)},
  clear_table(name){this.doc[name]=[]},add_child(name){const row={name:'fresh-'+(++sequence)};this.doc[name].push(row);return row},
});
}""")
		for path in ("c4factory/public/js/doctype/part_list_versions.js", "c4factory/c4factory/doctype/part_list/part_list.js"):
			page.add_script_tag(path=str(ROOT / path))
		page.evaluate("async()=>{window.frm=makeForm(1);configurePartListVersionActions(frm);await frm.buttons['New Version']()}")
		new = page.evaluate("newDraft")
		assert new["version_of"] == "TARGET" and new["docstatus"] == 0
		assert new["pds_table"][0]["arttach"] == "/private/files/design.pdf"
		assert new["panel_materials"][0]["name"].startswith("child-")
		page.evaluate("()=>{window.frm=makeForm(0);configurePartListVersionActions(frm);frm.buttons['Import Part List']()}")
		page.locator("[data-field=item_line]").select_option("Standard Lines")
		page.locator("[data-field=apply]").click()
		page.locator("input[name=part-list-source]").check()
		page.get_by_text("Open Movable Preview", exact=True).click()
		header = page.locator(".card-header")
		box = header.bounding_box()
		page.mouse.move(box["x"] + 70, box["y"] + 15)
		page.mouse.down()
		page.mouse.move(180, 160, steps=8)
		page.mouse.up()
		assert header.bounding_box()["x"] < box["x"] - 100
		if args.screenshot:
			page.screenshot(path=args.screenshot)
		page.locator("button[aria-label=Close]").click()
		page.locator("[data-primary]").click()
		page.wait_for_function("frm.doc.__unsaved === 1")
		copied = page.evaluate("frm.doc")
		assert copied["name"] == "TARGET" and copied["version_of"] == "ORIGINAL"
		assert copied["material_line"] == "Custom Material"
		assert copied["description"] == "Imported description"
		assert copied["pds_table"][0]["arttach"] == "/private/files/design.pdf"
		assert copied["panel_materials"][0]["qty"] == 3
		page.evaluate("async()=>{await frm.set_value({material_line:'User Override'});frm.doc.panel_materials[0].qty=9}")
		assert page.evaluate("frm.doc.metal_material_line") == "User Override"
		assert page.evaluate("frm.doc.panel_materials[0].qty") == 9
		assert not errors, errors
		browser.close()
	print("PASS: new-version draft, fresh child identities, selector import, retained PDS links, editable values, and draggable preview")


if __name__ == "__main__":
	main()
