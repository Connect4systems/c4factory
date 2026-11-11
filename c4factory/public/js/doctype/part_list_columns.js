// Shared document grid preferences. Never change shared child DocType metadata.
(() => {
  // Store independent preferences per Part List table and user.
  const settings_key = () => "C4TableColumns";
  const is_picture = (df) => ["picture", "image", "image_view", "image_preview"].includes(df.fieldname);
  const width = (value) => Math.min(10, Math.max(1, Math.trunc(Number(value) || 2)));
  function contain_table(grid) {
    if (!grid.wrapper) return;
    grid.wrapper.addClass("c4-table-columns");
    const table = grid.wrapper.find(".form-grid").first();
    // Older Frappe releases do not provide .form-grid-container.
    if (table.length && !table.parent().hasClass("c4-table-scroll")) {
      table.wrap('<div class="c4-table-scroll" tabindex="0"></div>');
    }
    grid.wrapper.parents(".form-column, .section-body, .form-section, .tab-pane")
      .css("min-width", "0");
  }

  function allowed(frm, df) {
    return df && !df.hidden && frm.get_perm(df.permlevel || 0, "read") &&
      (!frappe.model.no_value_type.includes(df.fieldtype) || df.fieldtype === "Button" ||
        (is_picture(df) && df.fieldtype === "Image"));
  }

  function setup(frm, grid) {
    if (grid.__c4_columns) return;
    grid.__c4_columns = true;
    grid.docfields = (grid.docfields || []).map((df) => ({ ...df }));
    const defaults = (grid.docfields || []).map((df) => ({ ...df }));

    grid.setup_visible_columns = function () {
      // setup_fields can replace grid.docfields on subsequent refreshes.
      const saved = frappe.get_user_settings(frm.doctype, settings_key(frm))?.[grid.df.fieldname];
      // Retain existing native preferences until this table has its own selection.
      const legacy = frappe.get_user_settings(frm.doctype, "GridView")?.[grid.doctype];
      const selection = Array.isArray(saved) ? saved : legacy;
      const fields = Array.isArray(selection) && selection.length
        ? selection.map((col) => {
          const df = grid.docfields.find((field) => field.fieldname === col.fieldname);
          return df && { ...df, columns: width(col.columns), in_list_view: 1 };
        }).filter((df) => allowed(frm, df))
        : defaults.filter((df) => df.in_list_view).map((df) => {
          const current = grid.docfields.find((field) => field.fieldname === df.fieldname);
          return current && { ...current, columns: df.columns };
        }).filter((df) => allowed(frm, df));
      grid.user_defined_columns = fields;
      grid.visible_columns = fields.map((df) => {
        if (!df.columns) grid.update_default_colsize(df);
        df.colsize = width(df.columns || df.colsize);
        return [df, df.colsize];
      });
      if (grid.wrapper) {
        contain_table(grid);
        const units = grid.visible_columns.reduce((sum, col) => sum + col[1], 0);
        grid.wrapper.find(".form-grid").css("min-width", `${units * 110 + 120}px`);
      }
    };

    const make_head = grid.make_head;
    grid.make_head = function (...args) {
      const result = make_head.apply(this, args);
      const header = grid.header_row;
      if (!header) return result;
      header.validate_columns_width = function () {
        if (!this.selected_columns_for_grid?.length) {
          frappe.throw(__("Select at least one column."));
        }
        this.selected_columns_for_grid.forEach((col) => { col.columns = width(col.columns); });
      };
      // The native picker must apply the same visibility and permission checks.
      const prepare = header.prepare_columns_for_dialog;
      header.prepare_columns_for_dialog = function (...params) {
        const options = prepare.apply(this, params).filter((option) =>
          allowed(frm, grid.docfields.find((df) => df.fieldname === option.value)));
        // Native pickers omit Image fields. Expose the existing Image View field
        // without making the hidden image attachment field visible.
        grid.docfields.filter(is_picture).filter((df) => allowed(frm, df)).forEach((df) => {
          if (!options.some((option) => option.value === df.fieldname)) {
            options.push({ label: __(df.label), value: df.fieldname,
              checked: (params[0] || []).includes(df.fieldname) });
          }
        });
        return options;
      };
      async function save(columns) {
        const preferences = { ...(frappe.get_user_settings(frm.doctype, settings_key(frm)) || {}) };
        preferences[grid.df.fieldname] = columns;
        const response = await frappe.model.user_settings.save(frm.doctype, settings_key(frm), preferences);
        frappe.model.user_settings[frm.doctype] = response.message || response;
        grid.reset_grid();
      }
      // Keep the dialog open until the preference has actually been saved.
      const configure = header.configure_dialog_for_columns_selector;
      header.configure_dialog_for_columns_selector = function () {
        configure.call(this);
        this.grid_settings_dialog.set_primary_action(__("Update"), async () => {
          this.validate_columns_width();
          await save(this.selected_columns_for_grid);
          this.grid_settings_dialog.hide();
        });
        this.grid_settings_dialog.set_secondary_action(async () => {
          await save([]);
          this.grid_settings_dialog.hide();
        });
      };
      return result;
    };
    grid.reset_grid();
  }

  const events = {
    refresh(frm) {
      configurePartListMaterialColumns(frm);
      if (!document.getElementById("c4-table-columns-style")) {
        const style = document.createElement("style");
        style.id = "c4-table-columns-style";
        style.textContent = `
          .c4-table-columns .form-grid-container { width: 100%; min-width: 0; max-width: 100%; }
          .c4-table-columns { width: 100%; max-width: 100%; min-width: 0; }
          .c4-table-columns .c4-table-scroll {
            display: block; width: 100%; max-width: 100%; min-width: 0;
            overflow-x: auto; overscroll-behavior-x: contain;
          }
          .c4-table-columns .c4-table-thumbnail {
            display: block; width: 1cm; height: 1cm; max-width: 1cm;
            object-fit: contain; margin: 2px auto;
          }
          .c4-table-columns .grid-static-col[data-fieldname="picture"],
          .c4-table-columns .grid-static-col[data-fieldname="image"],
          .c4-table-columns .grid-static-col[data-fieldname="image_preview"],
          .c4-table-columns .grid-static-col[data-fieldname="image_view"] {
            height: auto; min-height: calc(1cm + 4px);
          }
          .c4-table-columns .form-grid { left: 0 !important; }
          /* The expanded editor must not inherit the scrolling table's width. */
          .c4-table-columns .grid-row-open > .form-in-grid {
            position: fixed;
            top: 12vh;
            left: 16px;
            right: 16px;
            width: auto;
            min-width: 0;
            max-width: 1200px;
            max-height: 80vh;
            max-height: 80dvh;
            margin: 0 auto;
            box-sizing: border-box;
            overflow-y: auto;
            overscroll-behavior: contain;
          }
          .c4-table-columns .form-in-grid .grid-form-heading {
            position: sticky;
            top: calc(-1 * var(--padding-sm));
            z-index: 2;
            background: var(--modal-bg);
          }
          .c4-table-columns .form-in-grid .grid-header-toolbar {
            flex-wrap: wrap;
            gap: 8px;
          }
          @media (max-width: 575px) {
            .c4-table-columns .grid-row-open > .form-in-grid {
              left: 8px;
              right: 8px;
              top: 8vh;
              max-height: 88vh;
              max-height: 88dvh;
            }
          }
          .c4-table-columns .grid-row > .row { flex-wrap: nowrap; }
          .c4-table-columns .grid-row > .row > .col { flex: 0 0 40px; width: 40px; max-width: 40px; }
          ${Array.from({ length: 10 }, (_, i) => `
            .c4-table-columns .grid-row > .row > .col-xs-${i + 1} {
              flex: 0 0 ${(i + 1) * 110}px; width: ${(i + 1) * 110}px; max-width: ${(i + 1) * 110}px;
            }`).join("\n")}
        `;
        document.head.appendChild(style);
      }
      Object.values(frm.fields_dict).forEach((control) => {
        if (control.grid) {
          setup(frm, control.grid);
        }
      });
    },
  };
  ["Part List"].forEach((doctype) => frappe.ui.form.on(doctype, events));
})();
