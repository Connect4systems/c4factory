// c4napata/public/js/doctype/sales_order/request_bom.js
frappe.ui.form.on('Sales Order', {
  setup(frm) {
    configureSalesOrderPartListQueries(frm);
  },
  onload_post_render(frm) {
    configureSalesOrderPartListQueries(frm);
    if (frm.doc.docstatus !== 0) return;
    return Promise.all((frm.doc.items || []).map(row =>
      setSalesOrderDefaultPartList(frm, row.doctype, row.name, false)
    ));
  },
  refresh(frm) {
    configureSalesOrderPartListQueries(frm);
    if (!frm.is_new()) {
      frm.add_custom_button(__('Request PDS'), async () => {
        if (frm.is_dirty()) await frm.save();
        if (frm.is_dirty()) return;
        const result = await frappe.call({
          method: 'c4factory.api.pds_request.make_pds_request',
          args: { sales_order: frm.doc.name },
          freeze: true,
        });
        if (!result.message) return;
        const doc = frappe.model.sync(result.message)[0];
        frappe.set_route('Form', doc.doctype, doc.name);
      }, __('Create'));
      frm.add_custom_button(__('Request BOM'), async () => {
        // The mapper runs on the server, so save any specification changes first.
        // Otherwise it would read the previous values from the database.
        if (frm.is_dirty()) {
          await frm.save();
        }

        if (frm.is_dirty()) return;

        frappe.call({
          method: 'c4factory.api.contract_bom.make_contract_bom_request',
          args: { sales_order: frm.doc.name },
          freeze: true,
          callback: (r) => {
            if (!r.message) return;
            const doc = frappe.model.sync(r.message)[0]; // local unsaved doc
            frappe.set_route('Form', doc.doctype, doc.name);
          }
        });
      }, __('Create'));
    }
  }
});

// Each row keeps its own request so delayed responses cannot replace a manual choice.
const salesOrderPartListRequests = new WeakMap();

function salesOrderPartListFields(frm) {
  return (frm.fields_dict.items?.grid?.docfields || []).filter(field =>
    field.fieldtype === 'Link' && field.options === 'Part List'
  ).map(field => field.fieldname);
}

function configureSalesOrderPartListQueries(frm) {
  for (const field of salesOrderPartListFields(frm)) {
    frm.set_query(field, 'items', (doc, cdt, cdn) => ({
      filters: {
        product: locals[cdt]?.[cdn]?.item_code || '',
        disable: 0,
        docstatus: 1,
      },
    }));
  }
}

async function setSalesOrderDefaultPartList(frm, cdt, cdn, clear) {
  const row = locals[cdt]?.[cdn];
  const fields = salesOrderPartListFields(frm);
  if (!row || !fields.length) return;
  const item = row.item_code;
  const request = { applying: true, cancelled: false };
  salesOrderPartListRequests.set(row, request);
  if (clear) {
    for (const field of fields) await frappe.model.set_value(cdt, cdn, field, null);
  }
  request.applying = false;
  if (!item || salesOrderPartListRequests.get(row) !== request || row.item_code !== item ||
      fields.every(field => row[field])) return;
  const partLists = await frappe.db.get_list('Part List', {
    fields: ['name'],
    filters: { product: item, is_default: 1, disable: 0, docstatus: 1 },
    order_by: 'name asc',
    limit: 1,
  });
  if (salesOrderPartListRequests.get(row) !== request || request.cancelled ||
      row.item_code !== item || locals[cdt]?.[cdn] !== row || !partLists.length) return;
  request.applying = true;
  try {
    for (const field of fields) {
      if (!row[field]) await frappe.model.set_value(cdt, cdn, field, partLists[0].name);
    }
  } finally {
    request.applying = false;
  }
}

function cancelSalesOrderPartListLookup(frm, cdt, cdn) {
  const row = locals[cdt]?.[cdn];
  const request = row && salesOrderPartListRequests.get(row);
  if (request && !request.applying) request.cancelled = true;
}

frappe.ui.form.on('Sales Order Item', {
  item_code(frm, cdt, cdn) {
    return setSalesOrderDefaultPartList(frm, cdt, cdn, true);
  },
  custom_part_list: cancelSalesOrderPartListLookup,
  part_list: cancelSalesOrderPartListLookup,
});
