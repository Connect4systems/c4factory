frappe.ui.form.on('Work Order', {
    refresh: function(frm) {
        // Add "Create Pick List" button for submitted Work Orders
        if (frm.doc.docstatus === 1 && frm.doc.c4_required_items && frm.doc.c4_required_items.length > 0) {
            frm.add_custom_button(__('Create Pick List'), function() {
                create_pick_list_from_work_order(frm);
            }, __('Create'));
            
            // Add button to show balance
            frm.add_custom_button(__('Show Balance'), function() {
                show_work_order_balance(frm);
            }, __('View'));
        }
        
        // Show Pick Lists in dashboard
        if (frm.doc.docstatus === 1) {
            show_pick_lists_in_dashboard(frm);
        }
    }
});

function create_pick_list_from_work_order(frm) {
    frappe.call({
        method: 'c4factory.api.work_order_pick_list.make_pick_list',
        args: {
            work_order_id: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Creating Pick List...'),
        callback: function(r) {
            if (r.message) {
                // Open the new Pick List
                frappe.model.sync(r.message);
                frappe.set_route('Form', 'Pick List', r.message.name);
            }
        }
    });
}

function show_work_order_balance(frm) {
    frappe.call({
        method: 'c4factory.api.work_order_pick_list.get_work_order_balance',
        args: {
            work_order_id: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                show_balance_dialog(r.message);
            }
        }
    });
}

function show_balance_dialog(balance_data) {
    let html = `
        <div class="balance-summary">
            <h4>Balance Summary</h4>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>Item Code</th>
                        <th>Item Name</th>
                        <th>Required Qty</th>
                        <th>Picked Qty</th>
                        <th>Balance Qty</th>
                        <th>UOM</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    balance_data.items.forEach(function(item) {
        let balance_class = item.balance_qty > 0 ? 'text-warning' : 'text-success';
        html += `
            <tr>
                <td>${item.item_code}</td>
                <td>${item.item_name || ''}</td>
                <td>${item.required_qty}</td>
                <td>${item.picked_qty}</td>
                <td class="${balance_class}"><strong>${item.balance_qty}</strong></td>
                <td>${item.stock_uom}</td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
                <tfoot>
                    <tr>
                        <th colspan="2">Total</th>
                        <th>${balance_data.total_required}</th>
                        <th>${balance_data.total_picked}</th>
                        <th class="${balance_data.total_balance > 0 ? 'text-warning' : 'text-success'}">
                            <strong>${balance_data.total_balance}</strong>
                        </th>
                        <th></th>
                    </tr>
                </tfoot>
            </table>
        </div>
    `;
    
    frappe.msgprint({
        title: __('Work Order Balance'),
        message: html,
        wide: true
    });
}

function show_pick_lists_in_dashboard(frm) {
    // Show related Pick Lists
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Pick List',
            filters: {
                c4_work_order: frm.doc.name
            },
            fields: ['name', 'docstatus', 'c4_status', 'c4_total_qty', 'c4_balance_qty', 'creation'],
            order_by: 'creation desc'
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                let html = '<div class="pick-lists-summary"><h5>Pick Lists</h5><ul class="list-unstyled">';
                
                r.message.forEach(function(pl) {
                    let status_class = pl.docstatus === 1 ? 'text-success' : 'text-muted';
                    let c4_status_class = pl.c4_status === 'Completed' ? 'text-success' : 'text-warning';
                    
                    html += `
                        <li>
                            <a href="/app/pick-list/${pl.name}">${pl.name}</a>
                            <span class="${status_class}"> (${pl.docstatus === 1 ? 'Submitted' : 'Draft'})</span>
                            <span class="${c4_status_class}"> - ${pl.c4_status || 'Open'}</span>
                            - Qty: ${pl.c4_total_qty || 0}, Balance: ${pl.c4_balance_qty || 0}
                        </li>
                    `;
                });
                
                html += '</ul></div>';
                
                frm.dashboard.add_section(html, __('Related Pick Lists'));
            }
        }
    });
}
