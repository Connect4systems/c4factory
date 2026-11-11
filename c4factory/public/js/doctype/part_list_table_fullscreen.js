// Present the live field in a dialog; never create a second editable child table.
(() => {
  let active;

  function add_styles() {
    if (document.getElementById("c4-part-list-fullscreen-style")) return;
    $("<style>", { id: "c4-part-list-fullscreen-style", text: `
      .c4-part-list-fullscreen .modal-dialog { width:100%; max-width:none; margin:0; height:100vh; height:100dvh; }
      .c4-part-list-fullscreen .modal-content { height:100%; max-height:none; border:0; border-radius:0; }
      .c4-part-list-fullscreen .modal-header { flex-shrink:0; border-bottom:1px solid var(--border-color); }
      .c4-part-list-fullscreen .modal-body { display:flex; flex-direction:column; flex:1; min-height:0; max-height:none; overflow:hidden; padding:16px; }
      .c4-part-list-fullscreen .modal-footer { display:none; }
      .c4-fullscreen-navigation, .c4-fullscreen-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; flex-shrink:0; }
      .c4-fullscreen-navigation { margin-bottom:12px; }
      .c4-fullscreen-navigation .c4-fullscreen-hint { flex:1; color:var(--text-muted); font-size:12px; }
      .c4-part-list-fullscreen .btn { border-radius:8px; }
      .c4-fullscreen-field, .c4-fullscreen-field > .form-group,
      .c4-fullscreen-field .control-input-wrapper, .c4-fullscreen-field .control-input,
      .c4-fullscreen-field .c4-table-columns, .c4-fullscreen-field .form-grid-container {
        display:flex; flex-direction:column; flex:1; min-height:0; min-width:0;
      }
      .c4-fullscreen-field { margin-bottom:0; }
      .c4-quotation-sticky .c4-table-scroll { max-height:65vh; overflow:auto; }
      .c4-fullscreen-field .c4-quotation-sticky .c4-table-scroll { max-height:none; }
      .c4-fullscreen-field .c4-table-scroll { flex:1; min-height:0; overflow:auto; overscroll-behavior:contain; }
      .c4-fullscreen-field .c4-table-scroll { scrollbar-color:#8b1e2d #f3e7e9; scrollbar-width:auto; }
      .c4-fullscreen-field .c4-table-scroll::-webkit-scrollbar { width:12px; height:12px; }
      .c4-fullscreen-field .c4-table-scroll::-webkit-scrollbar-track,
      .c4-fullscreen-field .c4-table-scroll::-webkit-scrollbar-corner { background:#f3e7e9; }
      .c4-fullscreen-field .c4-table-scroll::-webkit-scrollbar-thumb { background:#8b1e2d; border:2px solid #f3e7e9; border-radius:8px; }
      .c4-fullscreen-field .c4-table-scroll::-webkit-scrollbar-thumb:hover { background:#681622; }
      .c4-boq-submitted > .grid-row .data-row,
      .c4-boq-submitted > .data-row { background:var(--green-100, #e4f5e9); box-shadow:inset 3px 0 var(--green-500, #28a745); }
      .c4-quotation-sticky .grid-heading-row,
      .c4-fullscreen-field .grid-heading-row { position:sticky; top:0; z-index:3; background:var(--fg-color, white); box-shadow:0 1px 0 var(--border-color); }
      .c4-fullscreen-actions { padding:8px 0; }
      .c4-fullscreen-actions .grid-footer { margin:0; width:100%; }
      .c4-fullscreen-actions .mb-3, .c4-fullscreen-actions .mb-2 { margin-bottom:0 !important; }
      .c4-part-list-fullscreen .c4-fullscreen-field .form-grid-container { overflow:visible; }
      @media(max-width:575px) { .c4-part-list-fullscreen .modal-body { padding:8px; } }
    ` }).appendTo(document.head);
  }

  function open_table(frm, field, opener) {
    if (active) return;
    const grid = field.grid;
    const wrapper = $(field.$wrapper || field.wrapper);
    const marker = document.createComment("part list table location");
    wrapper[0].before(marker);
    const focus = document.activeElement;
    const moved = [];
    const dialog = new frappe.ui.Dialog({ title: __(field.df.label || "Items"), fields: [] });
    const modal = dialog.$wrapper;
    modal.addClass("c4-part-list-fullscreen");
    // Preserve delegated form/grid handlers while the field is displayed in the modal.
    modal.appendTo(frm.wrapper);
    const body = modal.find(".modal-body");
    const navigation = $('<div class="c4-fullscreen-navigation">').appendTo(body);
    $('<span class="c4-fullscreen-hint">').text(__("Edits update this document directly. Save as usual.")).appendTo(navigation);
    const scroll = () => grid.wrapper.find(".c4-table-scroll")[0];
    for (const [label, direction] of [["Scroll left", -1], ["Scroll right", 1]]) {
      $('<button type="button" class="btn btn-default btn-sm">')
        .text(direction < 0 ? "←" : "→").attr({ "aria-label": __(label), title: __(label) })
        .on("click", () => {
          const viewport = scroll();
          if (viewport) viewport.scrollBy({ left: direction * Math.max(220, viewport.clientWidth * 0.7), behavior: "smooth" });
        }).appendTo(navigation);
    }
    $('<button type="button" class="btn btn-primary btn-sm">').text(__("Close"))
      .on("click", () => dialog.hide()).appendTo(navigation);
    const actions = $('<div class="c4-fullscreen-actions">').appendTo(body);
    wrapper.addClass("c4-fullscreen-field").appendTo(body);
    opener.hide();

    function move_actions() {
      // Move native controls with their handlers and visibility rules intact.
      const candidates = [grid.c4_manage_price_button, grid.c4_ask_price_button,
        ...grid.wrapper.find(".grid-footer").toArray()];
      for (const candidate of candidates) {
        const element = $(candidate);
        if (!element.length || actions[0].contains(element[0])) continue;
        const placeholder = document.createComment("part list table action location");
        element[0].before(placeholder);
        moved.push({ element, placeholder });
        element.appendTo(actions);
      }
    }
    move_actions();
    const observer = new MutationObserver(move_actions);
    observer.observe(wrapper[0], { childList:true, subtree:true });
    active = { dialog };
    let restored = false;
    function restore() {
      if (restored) return;
      restored = true;
      observer.disconnect();
      for (const { element, placeholder } of moved.reverse()) {
        if (placeholder.parentNode) placeholder.replaceWith(element[0]);
      }
      wrapper.removeClass("c4-fullscreen-field");
      marker.replaceWith(wrapper[0]);
      opener.show();
      active = null;
      modal.remove();
      if (focus?.isConnected) focus.focus();
    }
    modal.one("hidden.bs.modal", restore);
    const route_change = () => dialog.hide();
    frappe.router.on("change", route_change);
    modal.one("hidden.bs.modal", () => frappe.router.off("change", route_change));
    dialog.show();
  }

  function initialize_tables(frm) {
    add_styles();
    for (const field of Object.values(frm.fields_dict || {})) {
      if (!field.grid?.wrapper?.length) continue;
      field.grid.wrapper.addClass("c4-quotation-sticky");
      if (field.grid.c4_fullscreen_button) continue;
      const button = $('<button type="button" class="btn btn-default btn-sm mb-2">')
        .text(__("Open full screen")).attr("aria-haspopup", "dialog")
        .on("click", () => open_table(frm, field, button)).insertBefore(field.grid.wrapper);
      field.grid.c4_fullscreen_button = button;
    }
  }
  ["Part List"].forEach((doctype) => frappe.ui.form.on(doctype, {
    onload: initialize_tables,
    refresh: initialize_tables,
    onload_post_render: initialize_tables,
  }));
})();
