frappe.ui.form.on('Pick List', {
    refresh: function(frm) {
        // Add "Create Stock Entry" button for submitted Pick Lists with balance
        if (frm.doc.docstatus === 1 && frm.doc.c4_work_order && frm.doc.c4_balance_qty > 0) {
            // Material Transfer for Manufacture
            frm.add_custom_button(__('Material Transfer'), function() {
                create_stock_entry_from_pick_list(frm, 'Material Transfer for Manufacture');
            }, __('Create'));
            
            // Manufacture
            frm.add_custom_button(__('Manufacture'), function() {
                create_stock_entry_from_pick_list(frm, 'Manufacture');
            }, __('Create'));
            
            // Partial Stock Entry
            frm.add_custom_button(__('Partial Transfer'), function() {
                show_partial_transfer_dialog(frm);
            }, __('Create'));
        }
        
        // Show related Stock Entries
        if (frm.doc.docstatus === 1 && frm.doc.c4_work_order) {
            show_stock_entries_in_dashboard(frm);
        }
        
        // Add indicator for status
        if (frm.doc.c4_status) {
            frm.page.set_indicator(frm.doc.c4_status, frm.doc.c4_status === 'Completed' ? 'green' : 'orange');
        }
    }
});

function create_stock_entry_from_pick_list(frm, purpose) {
    frappe.call({
        method: 'c4factory.api.pick_list_stock.make_stock_entry',
        args: {
            pick_list_id: frm.doc.name,
            purpose: purpose
        },
        freeze: true,
        freeze_message: __('Creating Stock Entry...'),
        callback: function(r) {
            if (r.message) {
                // Open the new Stock Entry
                frappe.model.sync(r.message);
                frappe.set_route('Form', 'Stock Entry', r.message.name);
            }
        }
    });
}

function show_partial_transfer_dialog(frm) {
    // Get items with balance
    let items_with_balance = [];
    
    if (frm.doc.locations) {
        frm.doc.locations.forEach(function(item) {
            if (item.c4_balance_qty > 0) {
                items_with_balance.push({
                    item_code: item.item_code,
                    item_name: item.item_name,
                    balance_qty: item.c4_balance_qty,
                    uom: item.uom,
                    warehouse: item.warehouse
                });
            }
        });
    }
    
    if (items_with_balance.length === 0) {
        frappe.msgprint(__('No items with balance quantity'));
        return;
    }
    
    // Create dialog
    let d = new frappe.ui.Dialog({
        title: __('Partial Stock Entry'),
        fields: [
            {
                fieldname: 'purpose',
                label: __('Purpose'),
                fieldtype: 'Select',
                options: 'Material Transfer for Manufacture\nManufacture',
                default: 'Material Transfer for Manufacture',
                reqd: 1
            },
            {
                fieldname: 'items_section',
                label: __('Select Items and Quantities'),
                fieldtype: 'Section Break'
            },
            {
                fieldname: 'items_html',
                fieldtype: 'HTML'
            }
        ],
        primary_action_label: __('Create Stock Entry'),
        primary_action: function(values) {
            // Collect selected items with quantities
            let items = [];
            items_with_balance.forEach(function(item) {
                let qty_input = d.fields_dict.items_html.$wrapper.find(`input[data-item="${item.item_code}"]`);
                let qty = parseFloat(qty_input.val() || 0);
                
                if (qty > 0) {
                    items.push({
                        item_code: item.item_code,
                        qty: qty
                    });
                }
            });
            
            if (items.length === 0) {
                frappe.msgprint(__('Please enter quantities for at least one item'));
                return;
            }
            
            // Create Stock Entry
            frappe.call({
                method: 'c4factory.api.pick_list_stock.make_partial_stock_entry',
                args: {
                    pick_list_id: frm.doc.name,
                    items_json: JSON.stringify(items),
                    purpose: values.purpose
                },
                freeze: true,
                freeze_message: __('Creating Partial Stock Entry...'),
                callback: function(r) {
                    if (r.message) {
                        d.hide();
                        frappe.model.sync(r.message);
                        frappe.set_route('Form', 'Stock Entry', r.message.name);
                    }
                }
            });
        }
    });
    
    // Build HTML for items
    let html = `
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>${__('Item Code')}</th>
                    <th>${__('Item Name')}</th>
                    <th>${__('Balance Qty')}</th>
                    <th>${__('UOM')}</th>
                    <th>${__('Qty to Transfer')}</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    items_with_balance.forEach(function(item) {
        html += `
            <tr>
                <td>${item.item_code}</td>
                <td>${item.item_name || ''}</td>
                <td>${item.balance_qty}</td>
                <td>${item.uom}</td>
                <td>
                    <input type="number" 
                           class="form-control" 
                           data-item="${item.item_code}"
                           min="0" 
                           max="${item.balance_qty}" 
                           step="0.01"
                           value="${item.balance_qty}"
                           style="width: 120px;">
                </td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    d.fields_dict.items_html.$wrapper.html(html);
    d.show();
}

function show_stock_entries_in_dashboard(frm) {
    // Show related Stock Entries
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Stock Entry',
            filters: {
                c4_pick_list: frm.doc.name
            },
            fields: ['name', 'docstatus', 'stock_entry_type', 'posting_date', 'total_amount'],
            order_by: 'posting_date desc'
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                let html = '<div class="stock-entries-summary"><h5>Stock Entries</h5><ul class="list-unstyled">';
                
                r.message.forEach(function(se) {
                    let status_class = se.docstatus === 1 ? 'text-success' : 'text-muted';
                    let status_text = se.docstatus === 1 ? 'Submitted' : se.docstatus === 2 ? 'Cancelled' : 'Draft';
                    
                    html += `
                        <li>
                            <a href="/app/stock-entry/${se.name}">${se.name}</a>
                            <span class="${status_class}"> (${status_text})</span>
                            - ${se.stock_entry_type}
                            - ${se.posting_date}
                            ${se.total_amount ? ' - Amount: ' + se.total_amount : ''}
                        </li>
                    `;
                });
                
                html += '</ul></div>';
                
                frm.dashboard.add_section(html, __('Related Stock Entries'));
            }
        }
    });
}
