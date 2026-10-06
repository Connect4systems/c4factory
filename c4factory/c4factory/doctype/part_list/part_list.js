const partMaterialColorRequests = new Map();

async function refreshPartListProductImage(frm) {
  const product = frm.doc.product;
  const request = (frm._productImageRequest || 0) + 1;
  frm._productImageRequest = request;
  frm.doc.product_image = null;
  frm.refresh_field("image");
  const result = product
    ? await frappe.db.get_value("Item", product, "image")
    : null;
  if (frm._productImageRequest !== request || frm.doc.product !== product) return;
  frm.doc.product_image = result?.message?.image || null;
  frm.refresh_field("image");
}

async function syncPartMaterialColor(frm, cdt, cdn, clear = false) {
  const row = locals[cdt]?.[cdn];
  if (!row) return;
  const material = row.material;
  const request = (partMaterialColorRequests.get(cdn) || 0) + 1;
  partMaterialColorRequests.set(cdn, request);
  if (clear) {
    await frappe.model.set_value(cdt, cdn, { basic_color: null, color_doctype: null });
  }
  const result = material
    ? await frappe.db.get_value("Part Material", material, "color")
    : null;
  if (partMaterialColorRequests.get(cdn) !== request || row.material !== material || !locals[cdt]?.[cdn]) return;
  const target = result?.message?.color || null;
  if (!target || row.color_doctype !== target) {
    await frappe.model.set_value(cdt, cdn, "basic_color", null);
  }
  await frappe.model.set_value(cdt, cdn, "color_doctype", target);
  frm.refresh_field("pick_list_materials");
}

frappe.ui.form.on("Part List", {
  refresh(frm) {
    return Promise.all([refreshPartListProductImage(frm), ...(frm.doc.pick_list_materials || []).map((row) =>
      syncPartMaterialColor(frm, row.doctype, row.name)
    )]);
  },
  product(frm) {
    return refreshPartListProductImage(frm);
  }
});

frappe.ui.form.on("Pick List Materials", {
  material(frm, cdt, cdn) {
    return syncPartMaterialColor(frm, cdt, cdn, true);
  }
});

// Part List item selectors use the same filtering API as BOM in c4pricing.
(() => {
  const SELECTOR_CONFIGS = [
    { label: __("Add Accessories"), parent_group: "Accessorise", target_table: "accessorise_table", item_field: "item", enable_color: false },
  ];
  const esc = frappe.utils.escape_html;

  async function addOrMergePartListItems(frm, config, items, values) {
    const added = [];
    const merged = [];
    for (const it of items) {
      const existingRow = (frm.doc[config.target_table] || []).find((row) =>
        row[config.item_field] === it.item_code && (!config.enable_color || (
          row.part_type === values.part_type &&
          ["width", "hight", "thickness"].every((field) => flt(row[field]) === flt(values[field]))
        ))
      );
      if (existingRow) {
        await frappe.model.set_value(existingRow.doctype, existingRow.name, "qty", flt(existingRow.qty) + 1);
        merged.push(it.item_code);
        continue;
      }

      const details = await frappe.db.get_value("Item", it.item_code, [
        "item_group", "description", "custom_basic_color",
      ]);
      const item = details.message || {};
      const row = frm.add_child(config.target_table);
      const rowValues = { [config.item_field]: it.item_code, qty: 1 };
      if (config.enable_color) {
        Object.assign(rowValues, {
          part_type: values.part_type,
          item_group: item.item_group,
          basic_color: item.custom_basic_color || "",
          width: flt(values.width),
          hight: flt(values.hight),
          thickness: flt(values.thickness),
        });
      } else {
        rowValues.description = item.description || "";
      }
      await frappe.model.set_value(row.doctype, row.name, rowValues);
      added.push(it.item_code);
    }
    frm.refresh_field(config.target_table);
    return { added, merged };
  }

  async function fetchBounds(parent_group) {
    const bounds = await frappe.call({
      method: "c4pricing.api.item_group_filters.bounds",
      args: { parent_group },
    });
    return bounds.message;
  }

  function debounce(fn, wait) {
    let timer = null;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  async function openPartListItemSelector(frm, config) {
    const d = new frappe.ui.Dialog({
      title: config.label,
      size: "extra-large",
      fields: [
        { fieldtype: "Section Break", label: __("Part Details"), hidden: !config.enable_color },
        { fieldtype: "Link", fieldname: "part_type", label: __("Part Type"), options: "Part Type", hidden: !config.enable_color },
        { fieldtype: "Float", fieldname: "width", label: __("Width"), hidden: !config.enable_color },
        { fieldtype: "Column Break" },
        { fieldtype: "Float", fieldname: "hight", label: __("Height"), hidden: !config.enable_color },
        { fieldtype: "Float", fieldname: "thickness", label: __("Thickness"), hidden: !config.enable_color },
        { fieldtype: "Section Break", label: __("Filters") },
        { fieldtype: "Column Break" },
        { fieldtype: "Link", fieldname: "item_group", label: __("Item Group"), options: "Item Group" },
        { fieldtype: "Column Break" },
        { fieldtype: "Link", fieldname: "color_doctype", options: "DocType", hidden: 1 },
        { fieldtype: "Dynamic Link", fieldname: "custom_color", label: __("Basic Color"), options: "color_doctype", hidden: 1 },
        { fieldtype: "Column Break" },
        { fieldtype: "Data", fieldname: "q", label: __("Search"), placeholder: __("Code, name, description") },
        { fieldtype: "Column Break" },
        { fieldtype: "Select", fieldname: "limit", label: __("Results per page"), options: "20\n50\n100", default: "50" },
        { fieldtype: "Button", fieldname: "apply", label: __("Apply") },
        { fieldtype: "Section Break" },
        { fieldtype: "HTML", fieldname: "results_html" },
      ],
      primary_action_label: __("Add"),
      primary_action: () => handleAdd(),
      secondary_action_label: __("Close"),
      secondary_action: () => d.hide(),
    });

    const $results = d.get_field("results_html").$wrapper;
    const selectedItems = new Map();
    let currentItems = [];
    let adding = false;

    $results.html(`
      <div style="max-height:520px;overflow:auto;border:1px solid var(--border-color);border-radius:8px">
        <table class="table table-bordered table-hover" style="margin:0">
          <thead>
            <tr>
              <th style="width:70px">${__("Select")}</th>
              <th>${__("Item Code")}</th>
              <th>${__("Item Name")}</th>
              <th>${__("Basic Color")}</th>
              <th>${__("UOM")}</th>
              <th>${__("Description")}</th>
              <th style="width:120px">${__("Qty")}</th>
              <th style="width:120px">${__("Rate")}</th>
            </tr>
          </thead>
          <tbody class="c4p-body"></tbody>
        </table>
      </div>
      <div class="d-flex justify-content-between align-items-center mt-2">
        <div class="text-muted c4p-selected-count"></div>
        <div class="c4p-pager">
          <button class="btn btn-xs btn-default c4p-prev">${__("Prev")}</button>
          <span class="c4p-page text-muted" style="margin:0 8px">1</span>
          <button class="btn btn-xs btn-default c4p-next">${__("Next")}</button>
        </div>
      </div>
    `);

    const $body = $results.find(".c4p-body");
    const $page = $results.find(".c4p-page");
    const $prev = $results.find(".c4p-prev");
    const $next = $results.find(".c4p-next");
    const $selectedCount = $results.find(".c4p-selected-count");
    let offset = 0;
    let hasMore = false;

    if (!config.enable_color) {
      d.get_field("custom_color").$wrapper.hide();
    }

    function updateSelectedCount() {
      $selectedCount.text(__("{0} item(s) selected.", [selectedItems.size]));
    }

    function renderItems(items) {
      $body.empty();

      if (!items.length) {
        $body.append(`<tr><td colspan="8" class="text-muted text-center">${__("No items found")}</td></tr>`);
        updateSelectedCount();
        return;
      }

      items.forEach((it) => {
        const checked = selectedItems.has(it.item_code) ? "checked" : "";
        $body.append(`
          <tr class="c4p-row" data-code="${esc(it.item_code)}" style="cursor:pointer">
            <td><input type="checkbox" class="c4p-check" data-code="${esc(it.item_code)}" ${checked}/></td>
            <td>${esc(it.item_code)}</td>
            <td>${esc(it.item_name || "")}</td>
            <td>${esc(it.basic_color ?? it.custom_basic_color ?? it.color ?? "")}</td>
            <td>${esc(it.uom || "")}</td>
            <td>${esc(it.description || "")}</td>
            <td>${frappe.format(it.available_qty || 0, { fieldtype: "Float" })}</td>
            <td>${frappe.format(it.rate || 0, { fieldtype: "Currency" })}</td>
          </tr>
        `);
      });

      $body.find(".c4p-row").on("click", function (e) {
        if ($(e.target).is("input")) return;
        const $check = $(this).find(".c4p-check");
        $check.prop("checked", !$check.prop("checked")).trigger("change");
      });

      $body.find(".c4p-check").on("change", function () {
        const code = this.dataset.code;
        const item = currentItems.find((candidate) => candidate.item_code === code);
        if (this.checked && item) selectedItems.set(code, item);
        else selectedItems.delete(code);
        updateSelectedCount();
      });

      updateSelectedCount();
    }

    async function refreshList() {
      if (colorLoading) return;
      const request = ++listRequest;
      const v = d.get_values();
      if (!v) return;
      const res = await frappe.call({
        method: "c4pricing.api.item_selector.get_bom_selector_items",
        args: {
          parent_group: config.parent_group,
          non_pricing_groups_only: 1,
          item_group: v.item_group,
          txt: v.q,
          basic_color: config.enable_color ? v.custom_color : null,
          limit: v.limit,
          offset,
          company: frm.doc.company || frappe.defaults.get_user_default("Company"),
          price_list: frm.doc.buying_price_list || "Standard Buying",
          posting_date: frm.doc.posting_date || frm.doc.transaction_date,
        },
      });

      if (request !== listRequest) return;
      currentItems = res.message?.items || [];
      hasMore = Boolean(res.message?.has_more);
      renderItems(currentItems);
      const pageIndex = Math.floor(offset / cint(v.limit || 50)) + 1;
      $page.text(pageIndex);
      $prev.prop("disabled", offset <= 0);
      $next.prop("disabled", !hasMore);
    }

    async function handleAdd() {
      if (!selectedItems.size) {
        frappe.msgprint(__("Please select at least one item."));
        return;
      }

      const items = Array.from(selectedItems.values());
      const values = d.get_values();
      if (!values) return;
      if (config.enable_color && !values.part_type) {
        frappe.msgprint(__("Please select a Part Type."));
        return;
      }
      if (adding) return;
      adding = true;
      d.get_primary_btn().prop("disabled", true);
      try {
        const result = await addOrMergePartListItems(frm, config, items, values);

        frappe.show_alert({
          message: __("Added {0} item(s); increased quantity for {1} existing item(s).", [
            result.added.length,
            result.merged.length,
          ]),
          indicator: "green",
        });
        d.hide();
      } finally {
        adding = false;
        d.get_primary_btn().prop("disabled", false);
      }
    }

    const bounds = await fetchBounds(config.parent_group);
    d.fields_dict.item_group.get_query = () => ({
      filters: [
        ["lft", ">", bounds.lft],
        ["rgt", "<", bounds.rgt],
        ["custom_pricing", "=", 0],
      ],
    });

    const refreshFromFirstPage = () => {
      offset = 0;
      refreshList();
    };
    const debouncedSearch = debounce(refreshFromFirstPage, 300);

    let colorLoading = false;
    let colorRequest = 0;
    let listRequest = 0;
    d.fields_dict.item_group.df.onchange = async () => {
      const request = ++colorRequest;
      ++listRequest;
      colorLoading = true;
      const group = d.get_value("item_group");
      d.set_df_property("custom_color", "hidden", 1);
      await d.set_value("custom_color", "");
      await d.set_value("color_doctype", "");
      try {
        const response = config.enable_color && group
          ? await frappe.db.get_value("Item Group", group, "custom_color")
          : null;
        if (request !== colorRequest) return;
        const source = response?.message?.custom_color || "";
        await d.set_value("color_doctype", source);
        d.set_df_property("custom_color", "hidden", !source);
      } finally {
        if (request === colorRequest) {
          colorLoading = false;
          refreshFromFirstPage();
        }
      }
    };
    ["custom_color", "limit"].forEach((fn) => {
      const f = d.fields_dict[fn];
      if (f) f.df.onchange = refreshFromFirstPage;
    });

    d.fields_dict.q?.$input?.on("input", debouncedSearch);
    d.fields_dict.q?.$input?.on("change", refreshFromFirstPage);

    d.get_field("apply").$input.on("click", () => {
      refreshFromFirstPage();
    });

    $prev.on("click", () => {
      const v = d.get_values();
      const lim = cint(v.limit || 50);
      offset = Math.max(0, offset - lim);
      refreshList();
    });

    $next.on("click", () => {
      const v = d.get_values();
      const lim = cint(v.limit || 50);
      if (!hasMore) return;
      offset = offset + lim;
      refreshList();
    });

    d.show();
    await refreshList();
  }

  frappe.ui.form.on("Part List", {
    refresh(frm) {
      if (frm.doc.docstatus !== 0 || frm.read_only) return;
      SELECTOR_CONFIGS.forEach((config) => {
        frm.add_custom_button(config.label, () => openPartListItemSelector(frm, config), __("Add"));
      });
    },
  });
})();
