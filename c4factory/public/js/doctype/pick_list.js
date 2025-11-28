// c4factory/public/js/doctype/pick_list.js

// C4Factory — Partial Stock Entry from Pick List
// ----------------------------------------------
// من Pick List (submitted) نقدر نعمل Stock Entry جزئي بناءً على
// balance الفعلي لكل صف، بدون ما نلمس منطق ERPNext الأصلي للـ Pick List.

frappe.ui.form.on("Pick List", {
  refresh(frm) {
    // نشتغل فقط لما تكون الوثيقة Submitted
    if (frm.doc.docstatus !== 1) return;

    frm.add_custom_button(
      __("Create Partial Stock Entry"),
      () => open_partial_se_dialog(frm),
      __("Factory")
    );
  },
});

// ----------------------------------------------
// Dialog logic
// ----------------------------------------------

async function open_partial_se_dialog(frm) {
  try {
    const { message } = await frappe.call({
      method: "c4factory.api.work_order_flow.get_pick_list_balance_rows",
      args: {
        pick_list: frm.doc.name,
      },
      freeze: true,
      freeze_message: __("Loading balance rows..."),
    });

    const rows = message || [];
    if (!rows.length) {
      frappe.msgprint(__("No remaining balance to transfer for this Pick List."));
      return;
    }

    const d = new frappe.ui.Dialog({
      title: __("Create Partial Stock Entry"),
      size: "large",
      primary_action_label: __("Create Stock Entry"),
      primary_action: () => submit_partial_se(frm, d, rows),
    });

    // نبني جدول HTML بسيط
    const $wrapper = d.body;
    $wrapper.innerHTML = `
      <div class="partial-se-wrapper">
        <table class="table table-bordered table-sm" style="margin-top: 10px;">
          <thead>
            <tr>
              <th style="width:40px; text-align:center;">
                <input type="checkbox" data-role="select-all">
              </th>
              <th>${__("Item Code")}</th>
              <th>${__("Item Name")}</th>
              <th style="width:120px; text-align:right;">${__("Balance Qty")}</th>
              <th style="width:140px; text-align:right;">${__("Transfer Qty")}</th>
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (r, idx) => `
              <tr data-idx="${idx}">
                <td style="text-align:center;">
                  <input type="checkbox" data-role="row-select" data-idx="${idx}">
                </td>
                <td>${frappe.utils.escape_html(r.item_code || "")}</td>
                <td>${frappe.utils.escape_html(r.item_name || "")}</td>
                <td style="text-align:right;">
                  ${frappe.format(r.balance_qty, { fieldtype: "Float", precision: 3 })}
                </td>
                <td style="text-align:right;">
                  <input type="number"
                         min="0"
                         step="0.001"
                         class="form-control input-sm"
                         data-role="transfer-qty"
                         data-idx="${idx}"
                         value="${r.balance_qty}">
                </td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;

    // select-all checkbox
    const selectAll = $wrapper.querySelector('input[data-role="select-all"]');
    if (selectAll) {
      selectAll.addEventListener("change", (e) => {
        const checked = e.target.checked;
        $wrapper
          .querySelectorAll('input[data-role="row-select"]')
          .forEach((cb) => (cb.checked = checked));
      });
    }

    d.show();
  } catch (e) {
    console.error(e);
    frappe.msgprint(__("Failed to load Pick List balances. See console for details."));
  }
}

// ----------------------------------------------
// Submit partial Stock Entry
// ----------------------------------------------

async function submit_partial_se(frm, dialog, rows) {
  const $wrapper = dialog.body;
  const items = [];

  rows.forEach((r, idx) => {
    const cb = $wrapper.querySelector(
      `input[data-role="row-select"][data-idx="${idx}"]`
    );
    if (!cb || !cb.checked) return;

    const qtyInput = $wrapper.querySelector(
      `input[data-role="transfer-qty"][data-idx="${idx}"]`
    );
    const qty = qtyInput ? parseFloat(qtyInput.value || "0") : 0;

    if (qty > 0) {
      items.push({
        pl_item_name: r.pl_item_name,
        qty,
      });
    }
  });

  if (!items.length) {
    frappe.msgprint(__("Please select at least one row with Transfer Qty > 0."));
    return;
  }

  try {
    const { message } = await frappe.call({
      method: "c4factory.api.work_order_flow.make_partial_stock_entry_from_pick_list",
      args: {
        pick_list: frm.doc.name,
        items_json: JSON.stringify(items),
      },
      freeze: true,
      freeze_message: __("Creating Stock Entry..."),
    });

    if (!message) {
      frappe.msgprint(__("Server did not return a Stock Entry name."));
      return;
    }

    dialog.hide();
    frappe.set_route("Form", "Stock Entry", message);
  } catch (e) {
    console.error(e);
    // Frappe عادةً يعرض رسالة الخطأ تلقائياً، بس نضيف رسالة عامة
    frappe.msgprint(__("Failed to create Stock Entry. Check server error log."));
  }
}
