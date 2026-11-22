async function fillDeliveryNoteDetails(frm) {
  if (frm.doc.docstatus !== 0) return;
  const projects = frm.doc.project ? [frm.doc.project] :
    [...new Set((frm.doc.items || []).map(row => row.project).filter(Boolean))];
  let projectNo = '';
  if (projects.length === 1) {
    const result = await frappe.db.get_value('Project', projects[0], 'custom_project_no');
    projectNo = result.message?.custom_project_no || '';
  }
  await frm.set_value('custom_project_no', projectNo);
  const orders = [...new Set((frm.doc.items || []).map(row => row.against_sales_order).filter(Boolean))];
  const sources = await Promise.all(orders.map(async name => {
    const result = await frappe.db.get_value('Sales Order', name, ['custom_project_title', 'custom_technical_team']);
    return result.message || {};
  }));
  for (const field of ['custom_project_title', 'custom_technical_team']) {
    const values = [...new Set(sources.map(source => source[field] || ''))];
    if (!frm.doc[field] && values.length === 1) await frm.set_value(field, values[0]);
  }
  await Promise.all((frm.doc.items || []).map(async row => {
    if (!row.so_detail || row.custom_note_initialized) return;
    const reference = row.so_detail;
    const result = await frappe.db.get_value('Sales Order Item', reference, ['parent', 'item_code', 'custom_note']);
    const source = result.message;
    if (row.so_detail !== reference || row.custom_note_initialized || !source ||
        source.parent !== row.against_sales_order || source.item_code !== row.item_code) return;
    if (!row.custom_note) await frappe.model.set_value(row.doctype, row.name, 'custom_note', source.custom_note || '');
    await frappe.model.set_value(row.doctype, row.name, 'custom_note_initialized', 1);
  }));
}

frappe.ui.form.on('Delivery Note', {
  refresh: fillDeliveryNoteDetails,
  project: fillDeliveryNoteDetails,
});
frappe.ui.form.on('Delivery Note Item', {
  project(frm) { return fillDeliveryNoteDetails(frm); },
  against_sales_order(frm) { return fillDeliveryNoteDetails(frm); },
  so_detail(frm) { return fillDeliveryNoteDetails(frm); },
});
