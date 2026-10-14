"""Browser check of partial Production Order creation; requires Playwright."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--jquery", required=True)
	args = parser.parse_args()
	with sync_playwright() as playwright:
		browser = playwright.chromium.launch(channel="msedge", headless=True)
		page = browser.new_page()
		page.set_content("<div id='dialog'></div>")
		page.add_script_tag(path=args.jquery)
		page.evaluate("""() => {
window.__ = text => text;
window.renderSalesOrderColors = () => {};
window.handlers = {};
window.messages = [];
window.requests = [];
window.available = [
  {color_sample_item:'ROW1',item_code:'DESK',item_name:'Desk',sample_qty:10,ordered_qty:3,remaining_qty:7,uom:'Nos'},
  {color_sample_item:'ROW2',item_code:'CHAIR',item_name:'Chair',sample_qty:5,ordered_qty:0,remaining_qty:5,uom:'Nos'},
  {color_sample_item:'ROW3',item_code:'TABLE',item_name:'Table',sample_qty:2,ordered_qty:2,remaining_qty:0,uom:'Nos'},
];
window.frappe = {
  ui:{form:{on(type, events){handlers[type]=events}}},
  model:{can_create:()=>true,sync:doc=>[doc]},
  utils:{escape_html:text=>$('<span>').text(text).html()},
  msgprint:message=>messages.push(message),
  set_route:(...route)=>window.lastRoute=route,
  async call(request){
    requests.push(request);
    if(request.method.endsWith('get_available_items'))return {message:available};
    return {message:{doctype:'Production Order',name:'new-production-order'}};
  },
  async set_value(){},
};
frappe.ui.Dialog=class {
  constructor(options){
    window.currentDialog=this;this.options=options;this.fields_dict={};
    const root=$('#dialog').empty();
    for(const field of options.fields){
      const wrapper=$('<div>').attr('data-field',field.fieldname).appendTo(root);
      const state={$wrapper:wrapper,value:field.default};this.fields_dict[field.fieldname]=state;
      if(field.fieldtype==='Select'){
        state.$input=$('<select>').appendTo(wrapper);
        for(const option of field.options)$('<option>').val(option.value).text(option.label).appendTo(state.$input);
        state.$input.val(field.default).on('change',()=>{state.value=state.$input.val();field.onchange?.()});
        // Real controls may emit a change while a dialog is being initialized.
        field.onchange?.();
      } else if(field.fieldtype==='Float'){
        state.$input=$('<input type="number">').val(field.default).appendTo(wrapper);
      }
    }
    $('<button id="create">Create</button>').appendTo(root).on('click',()=>options.primary_action({
      color_sample_item:this.get_value('color_sample_item'),qty:Number(this.get_value('qty')),
    }));
  }
  get_value(field){const state=this.fields_dict[field];return state.$input?.val()??state.value}
  set_value(field,value){const state=this.fields_dict[field];state.value=value;state.$input?.val(value)}
  disable_primary_action(){$('#create').prop('disabled',true)}
  enable_primary_action(){$('#create').prop('disabled',false)}
  show(){}hide(){$('#dialog').empty()}
};
window.makeForm=status=>({doc:{name:'SAMPLE',docstatus:status,items:[]},buttons:{},
  add_custom_button(label,action){this.buttons[label]=action}});
}""")
		errors = []
		page.on("pageerror", lambda error: errors.append(str(error)))
		page.add_script_tag(path=str(ROOT / "c4factory/c4factory/doctype/color_sample/color_sample.js"))
		page.evaluate("() => {window.frm=makeForm(0);handlers['Color sample'].refresh(frm)}")
		assert not page.evaluate("'Production Order' in frm.buttons")
		page.evaluate("async () => {window.frm=makeForm(1);handlers['Color sample'].refresh(frm);await frm.buttons['Production Order']()}")
		assert page.locator("select option").count() == 2
		assert page.locator("[data-field=qty] input").input_value() == "7"
		assert "Previously Ordered" in page.locator("[data-field=balance]").inner_text()
		page.locator("[data-field=qty] input").fill("8")
		page.locator("#create").click()
		assert page.evaluate("messages.length") == 1
		assert not page.evaluate("Boolean(window.lastRoute)")
		page.locator("select").select_option("ROW2")
		assert page.locator("[data-field=qty] input").input_value() == "5"
		page.locator("select").select_option("ROW1")
		page.locator("[data-field=qty] input").fill("4")
		page.locator("#create").click()
		page.wait_for_function("Boolean(window.lastRoute)")
		request = page.evaluate("requests.at(-1)")
		assert request["args"] == {"color_sample": "SAMPLE", "color_sample_item": "ROW1", "qty": 4}
		assert page.evaluate("lastRoute") == ["Form", "Production Order", "new-production-order"]
		page.evaluate("async () => {available=[];await frm.buttons['Production Order']()}")
		assert "already been allocated" in page.evaluate("messages.at(-1)")
		assert not errors, errors
		browser.close()
	print("PASS: submitted-sample action, balances, exhausted rows, quantity limits, partial order, and routing")


if __name__ == "__main__":
	main()
