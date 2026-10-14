function configurePartListVersionActions(frm) {
  frm.add_custom_button(__("Product Preview"), () => showPartListProductPreview({
    item_code: frm.doc.product, item_name: frm.doc.product_name,
    description: frm.doc.description, image: frm.doc.product_image,
    material_line: frm.doc.material_line, width: frm.doc.width, height: frm.doc.hight, depth: frm.doc.depth,
  }));
  frm.fields_dict.image?.$wrapper?.off("click.partListPreview").on("click.partListPreview", () =>
    showPartListProductPreview({item_code: frm.doc.product, item_name: frm.doc.product_name,
      description: frm.doc.description, image: frm.doc.product_image, material_line: frm.doc.material_line,
      width: frm.doc.width, height: frm.doc.hight, depth: frm.doc.depth}));
  if (frm.doc.docstatus === 1 && frappe.model.can_create("Part List")) {
    frm.add_custom_button(__("New Version"), async () => {
      const result = await frappe.call({method: "c4factory.api.part_list_versions.get_copy_payload",
        args: {source: frm.doc.name, new_version: 1}, freeze: true});
      await frappe.model.with_doctype("Part List");
      const doc = frappe.model.get_new_doc("Part List");
      const fields = frappe.get_meta("Part List").fields;
      for (const field of fields) {
        if (!(field.fieldname in result.message.values)) continue;
        const value = result.message.values[field.fieldname];
        if (["Table", "Table MultiSelect"].includes(field.fieldtype)) {
          doc[field.fieldname] = [];
          for (const values of value || []) {
            Object.assign(frappe.model.add_child(doc, field.options, field.fieldname), values);
          }
        } else doc[field.fieldname] = value;
      }
      doc.version_of = frm.doc.name;
      doc.is_default = 1;
      doc.__run_link_triggers = false;
      doc.__unsaved = 1;
      frappe.set_route("Form", "Part List", doc.name);
    }, __("Actions"));
  }
  if (frm.doc.docstatus === 0 && !frm.read_only) {
    frm.add_custom_button(__("Import Part List"), () => openImportPartListDialog(frm), __("Actions"));
  }
}

async function applyPartListCopy(frm, payload) {
  if (frm.doc.docstatus !== 0 || frm.read_only) throw new Error(__("Import requires an editable draft."));
  frm._productImageRequest = (frm._productImageRequest || 0) + 1;
  frm._applyingPartListCopy = true;
  try {
    const scalar = {};
    const tables = [];
    for (const field of frm.meta.fields) {
      if (["product", "product_name"].includes(field.fieldname)) continue;
      if (!(field.fieldname in payload.values)) continue;
      if (["Table", "Table MultiSelect"].includes(field.fieldtype)) tables.push(field);
      else scalar[field.fieldname] = payload.values[field.fieldname];
    }
    await frm.set_value(scalar);
    for (const field of tables) {
      frm.clear_table(field.fieldname);
      for (const values of payload.values[field.fieldname] || []) {
        Object.assign(frm.add_child(field.fieldname), values);
      }
      frm.refresh_field(field.fieldname);
    }
    frm.dirty();
    frm.refresh_fields();
  } finally { frm._applyingPartListCopy = false; }
}

let partListProductPreview = null;
function showPartListProductPreview(item) {
  if (partListProductPreview) partListProductPreview();
  const esc = frappe.utils.escape_html;
  const plain = document.createElement("div");
  plain.innerHTML = item.description || "";
  const panel = $("<div role='dialog' aria-label='Product Preview' tabindex='-1' class='card shadow'>")
    .css({position: "fixed", zIndex: 1090, top: "100px", right: "30px", width: "440px",
      maxWidth: "calc(100vw - 20px)", maxHeight: "calc(100vh - 30px)", overflow: "auto"})
    .appendTo(document.body);
  const header = $("<div class='card-header d-flex justify-content-between align-items-center'>")
    .css({cursor: "move", touchAction: "none"}).appendTo(panel);
  $("<strong>").text(__("Product Preview")).appendTo(header);
  const close = () => {
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", stop);
    panel.remove();
    partListProductPreview = null;
  };
  $("<button type='button' class='btn btn-xs btn-default' aria-label='Close'>×</button>")
    .appendTo(header).on("click", close);
  const body = $("<div class='card-body'>").appendTo(panel);
  body.html(`<div class="mb-1" style="font-weight:600">${esc(item.item_name || item.item_code || "")}</div>
    <div class="text-muted mb-2">${esc(item.item_code || "")}</div>
    ${item.image ? `<img style="max-width:100%;max-height:280px;object-fit:contain;border-radius:8px" src="${esc(frappe.urllib.get_full_url(item.image))}">` : ""}
    <div class="my-2" style="white-space:pre-wrap">${esc(plain.textContent || "")}</div>
    <div>${__("Material Line")}: ${esc(item.material_line || "-")}</div>
    <div>${__("Dimensions (W × H × D)")}: ${esc([item.width, item.height, item.depth].map(v => v ?? "-").join(" × "))}</div>`);
  let drag = null;
  function move(event) {
    if (!drag) return;
    const left = Math.max(0, Math.min(window.innerWidth - panel[0].offsetWidth, event.clientX - drag.x));
    const top = Math.max(0, Math.min(window.innerHeight - 40, event.clientY - drag.y));
    panel.css({left: `${left}px`, top: `${top}px`, right: "auto"});
  }
  function stop() { drag = null; }
  header.on("pointerdown", event => {
    if ($(event.target).closest("button").length) return;
    const rect = panel[0].getBoundingClientRect();
    drag = {x: event.clientX - rect.left, y: event.clientY - rect.top};
    event.preventDefault();
  });
  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", stop);
  panel.on("keydown", event => { if (event.key === "Escape") close(); });
  partListProductPreview = close;
  panel.trigger("focus");
}

var PART_LIST_ITEM_LINE_CONFIG = {
  "Standard Lines": { parent_group: "Standard Lines", include_children: true },
  "Customized Product": { parent_group: "Customized Product", include_children: false },
  "Upholstery": { parent_group: "Upholstery", include_children: true },
  "PU": { parent_group: "PU", include_children: true },
  "Outsource": { parent_group: "Outsource", include_children: true },
  "Home": { parent_group: "HOME", include_children: true },
  "Archi Touch Chairs": { parent_group: "Archi Chairs", include_children: true },
};

async function openImportPartListDialog(frm) {
  const state = { allowed_item_groups: [], current_page: 1, total_pages: 1 };
  const selected = new Map();

  const dialog = new frappe.ui.Dialog({
    title: __("Import Part List"),
    size: "extra-large",
    fields: [
      { fieldtype: "Section Break", label: __("Filters") },
      { fieldtype: "Column Break" },
      { label: __("Item Line"), fieldname: "item_line", fieldtype: "Select",
        options: ["", ...Object.keys(PART_LIST_ITEM_LINE_CONFIG)].join("\n"), reqd: 1 },
      { label: __("Material Line"), fieldname: "material_line", fieldtype: "Link", options: "Material Line" },
      { label: __("Search text"), fieldname: "q", fieldtype: "Data", placeholder: __("Part List ID, item code, name, description") },
      { fieldtype: "Column Break" },
      { label: __("Item Group"), fieldname: "item_group", fieldtype: "Link", options: "Item Group",
        get_query: () => ({
          filters: state.allowed_item_groups.length
            ? [["Item Group", "name", "in", state.allowed_item_groups]]
            : [["Item Group", "name", "=", ""]],
        }) },
      { label: __("Brand"), fieldname: "brand", fieldtype: "Link", options: "Brand" },
      { label: __("Results per page"), fieldname: "limit", fieldtype: "Select", options: "20\n50\n100", default: "20" },
      { fieldtype: "Column Break" },
      { label: __("Width (W)"), fieldname: "width", fieldtype: "Float" },
      { label: __("Height (H)"), fieldname: "height", fieldtype: "Float" },
      { label: __("Depth (D)"), fieldname: "depth", fieldtype: "Float" },
      { fieldtype: "Section Break" },
      { fieldtype: "Button", label: __("Apply Filters"), fieldname: "apply" },
      { fieldtype: "Section Break", label: __("Selector") },
      { fieldtype: "Column Break" },
      { fieldtype: "HTML", fieldname: "results_html" },
      { fieldtype: "Column Break" },
      { fieldtype: "HTML", fieldname: "preview_html" },
    ],
    primary_action_label: __("Import"),
    primary_action: async () => {
      if (!selected.size) {
        frappe.msgprint(__("Please select one Part List."));
        return;
      }

      const confirmed = await new Promise(resolve => frappe.confirm(
        __("Import details, PDS links, and all table contents from the selected Part List while keeping the current product?"),
        () => resolve(true), () => resolve(false),
      ));
      if (!confirmed) return;
      dialog.disable_primary_action();
      try {
        const response = await frappe.call({
          method: "c4factory.api.part_list_versions.get_copy_payload",
          args: { source: Array.from(selected.keys())[0], target: frm.is_new() ? null : frm.doc.name },
          freeze: true,
        });
        await applyPartListCopy(frm, response.message);
        dialog.hide();
        frappe.show_alert({ message: __("Part List imported. Review and save the draft."), indicator: "green" });
      } finally {
        dialog.enable_primary_action();
      }
    },
  });

  const esc = frappe.utils.escape_html;
  const $results = dialog.get_field("results_html").$wrapper;
  const $previewWrapper = dialog.get_field("preview_html").$wrapper;

  function resultsShell() {
    return `
      <div style="max-height:520px;overflow:auto;border:1px solid var(--border-color);border-radius:8px">
        <table class="table table-bordered table-hover" style="margin:0">
          <thead><tr>
            <th style="width:60px">${__("Select")}</th>
            <th>${__("Part List ID")}</th>
            <th>${__("Item Name")}</th>
            <th>${__("Material Line")}</th>
          </tr></thead>
          <tbody class="c4p-boq-body"></tbody>
        </table>
      </div>
      <div class="d-flex justify-content-between align-items-center mt-2">
        <div class="text-muted c4p-boq-selected"></div>
        <div class="c4p-boq-pagination" style="display:flex;align-items:center;gap:12px"></div>
      </div>`;
  }

  $results.html(resultsShell());
  $previewWrapper.html(`
    <div style="border:1px solid var(--border-color);border-radius:8px;min-height:520px;padding:10px">
      <div class="c4p-boq-preview-muted text-muted">${__("Hover or select a Part List to preview...")}</div>
      <div class="c4p-boq-preview"></div>
    </div>`);

  function stripHtml(html) {
    const element = document.createElement("div");
    element.innerHTML = html || "";
    return (element.textContent || element.innerText || "").trim();
  }

  function showPreview(item) {
    if (!item) return;
    const dimensions = [item.width, item.height, item.depth]
      .map((value) => (value === null || value === undefined || value === "" ? "-" : value))
      .join(" x ");
    const image = item.image
      ? `<div class="p-2"><img style="max-width:100%;max-height:280px;border-radius:8px" src="${esc(frappe.urllib.get_full_url(item.image))}"/></div>`
      : "";
    $previewWrapper.find(".c4p-boq-preview-muted").hide();
    $previewWrapper.find(".c4p-boq-preview").html(`
      <div class="p-2">
        <div class="mb-1" style="font-weight:600">${esc(item.item_name || item.item_code)}</div>
        <div class="text-muted mb-1">${esc(item.item_code || "")}</div>
        <div class="text-muted mb-2">${__("Part List ID")}: ${esc(item.part_list_id)}</div>
        ${image}
        <div class="mb-2" style="white-space:pre-wrap">${esc(stripHtml(item.description))}</div>
        <div><span class="text-muted">${__("Material Line")}:</span> ${esc(item.material_line || "-")}</div>
        <div><span class="text-muted">${__("Item Group")}:</span> ${esc(item.item_group || "-")}</div>
        <div><span class="text-muted">${__("Dimensions")}:</span> ${esc(dimensions)}</div>
        <div class="text-muted">${__("UOM")}: ${esc(item.uom || "-")}</div>
      </div>`);
    $previewWrapper.find("img").css("cursor", "zoom-in").on("click", () => showPartListProductPreview(item));
    $("<button class='btn btn-sm btn-default mt-2'>").text(__("Open Movable Preview"))
      .appendTo($previewWrapper.find(".c4p-boq-preview"))
      .on("click", () => showPartListProductPreview(item));
  }

  function updateSelectedCount() {
    $results.find(".c4p-boq-selected").text(__("{0} Part List(s) selected.", [selected.size]));
  }

  function updatePagination() {
    const $pagination = $results.find(".c4p-boq-pagination").empty();
    if (state.total_pages <= 1) return;
    const $previous = $(`<button class="btn btn-xs btn-secondary">${__("Previous")}</button>`);
    const $next = $(`<button class="btn btn-xs btn-secondary">${__("Next")}</button>`);
    $previous.prop("disabled", state.current_page <= 1);
    $next.prop("disabled", state.current_page >= state.total_pages);
    $previous.on("click", () => refreshList(state.current_page - 1));
    $next.on("click", () => refreshList(state.current_page + 1));
    $pagination.append($previous, `<span class="text-muted">${__("Page")} ${state.current_page} / ${state.total_pages}</span>`, $next);
  }

  function renderItems(items) {
    const $body = $results.find(".c4p-boq-body").empty();
    if (!items.length) {
      $body.append(`<tr><td colspan="4" class="text-muted text-center">${__("No related Part Lists found")}</td></tr>`);
      $previewWrapper.find(".c4p-boq-preview-muted").show();
      $previewWrapper.find(".c4p-boq-preview").empty();
      updateSelectedCount();
      updatePagination();
      return;
    }

    items.forEach((item) => {
      const entry = selected.get(item.part_list_id);
      $body.append(`
        <tr class="c4p-boq-row" data-part-list="${esc(item.part_list_id)}" style="cursor:pointer">
          <td><input type="radio" name="part-list-source" class="c4p-boq-check" data-part-list="${esc(item.part_list_id)}" ${entry ? "checked" : ""}/></td>
          <td>${esc(item.part_list_id)}</td>
          <td>${esc(item.item_name || "")}</td>
          <td>${esc(item.material_line || "")}</td>
        </tr>`);
    });

    $body.find(".c4p-boq-row").on("mouseenter click", function (event) {
      if ($(event.target).is("input")) return;
      showPreview(items.find((item) => item.part_list_id === this.dataset.partList));
    });
    $body.find(".c4p-boq-check").on("change", function () {
      const item = items.find((candidate) => candidate.part_list_id === this.dataset.partList);
      selected.clear();
      if (this.checked && item) selected.set(item.part_list_id, { item });
      updateSelectedCount();
      if (item) showPreview(item);
    });
    showPreview(items[0]);
    updateSelectedCount();
    updatePagination();
  }

  let listRequest = 0;
  async function refreshList(page = 1) {
    const request = ++listRequest;
    const values = {
      item_line: dialog.get_value("item_line"),
      material_line: dialog.get_value("material_line"),
      item_group: dialog.get_value("item_group"),
      brand: dialog.get_value("brand"),
      q: dialog.get_value("q"),
      width: dialog.get_value("width"),
      height: dialog.get_value("height"),
      depth: dialog.get_value("depth"),
      limit: dialog.get_value("limit"),
    };
    if (!values.item_line) {
      frappe.msgprint(__("Please select an Item Line, then click Apply Filters."));
      return;
    }
    const pageSize = cint(values.limit) || 20;
    state.current_page = Math.max(1, cint(page) || 1);
    const response = await frappe.call({
      method: "c4factory.api.part_list_versions.get_selector_items",
      args: {
        target: frm.is_new() ? null : frm.doc.name,
        item_line: values.item_line,
        material_line: values.material_line,
        item_group: values.item_group,
        brand: values.brand,
        txt: values.q,
        width: values.width,
        height: values.height,
        depth: values.depth,
        limit: pageSize,
        page: state.current_page,
      },
    });
    if (request !== listRequest) return;
    const result = response.message || {};
    const items = result.items || [];
    state.total_pages = Math.max(1, Math.ceil(cint(result.total) / pageSize));
    renderItems(items);
  }

  async function refreshAllowedItemGroups() {
    const config = PART_LIST_ITEM_LINE_CONFIG[dialog.get_value("item_line")];
    state.allowed_item_groups = [];
    if (!config) return;
    const result = await frappe.db.get_value("Item Group", config.parent_group, ["lft", "rgt", "is_group"]);
    const bounds = result?.message;
    if (!bounds) return;
    if (!config.include_children) {
      if (!cint(bounds.is_group)) state.allowed_item_groups = [config.parent_group];
      return;
    }
    const groups = await frappe.db.get_list("Item Group", {
      fields: ["name"],
      filters: [["lft", ">=", bounds.lft], ["rgt", "<=", bounds.rgt], ["is_group", "=", 0]],
      order_by: "lft asc",
      limit: 500,
    });
    state.allowed_item_groups = groups.map((group) => group.name);
  }

  dialog.fields_dict.item_line?.$input?.on("change", async () => {
    ++listRequest;
    selected.clear();
    updateSelectedCount();
    await refreshAllowedItemGroups();
    await dialog.set_value("item_group", null);
    state.current_page = 1;
    state.total_pages = 1;
    $results.find(".c4p-boq-body").empty();
    $results.find(".c4p-boq-pagination").empty();
    $previewWrapper.find(".c4p-boq-preview-muted").show();
    $previewWrapper.find(".c4p-boq-preview").empty();
  });
  dialog.get_field("apply").$input.on("click", async () => {
    if (!dialog.get_value("item_line")) {
      frappe.msgprint(__("Please select an Item Line, then click Apply Filters."));
      return;
    }
    selected.clear();
    await refreshAllowedItemGroups();
    await refreshList(1);
  });
  dialog.show();
}

