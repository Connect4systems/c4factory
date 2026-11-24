# c4factory/hooks.py

app_name = "c4factory"
app_title = "C4Factory"
app_publisher = "Connect 4 Systems"
app_description = "Factory App"
app_email = "info@connect4systems.com"
app_license = "mit"

# Reapply after customization sync, including sites that ran the original patch.
after_migrate = [
    "c4factory.patches.v1_0.setup_project_boq.execute",
    "c4factory.patches.v1_0.remove_item_colors.execute",
    "c4factory.patches.v1_0.setup_part_list_import.execute",
    "c4factory.patches.v1_0.remove_sales_order_header_colors.execute",
    "c4factory.patches.v1_0.allow_sales_order_part_list_after_submit.execute",
    "c4factory.patches.v1_0.move_part_file_to_pds_table.execute",
    "c4factory.patches.v1_0.repair_part_list_description.execute",
    "c4factory.patches.v1_0.setup_quotation_project_details.setup_fields",
    "c4factory.patches.v1_0.setup_project_sales_details.execute",
    "c4factory.patches.v1_0.setup_delivery_note_details.execute",
]

app_include_js = [
    "/assets/c4factory/js/doctype/project.js?v=20261122-boq-notes",
    "/assets/c4factory/js/doctype/part_list_columns.js?v=20261121-color-palette",
    "/assets/c4factory/js/doctype/part_list_table_fullscreen.js?v=20261111-scoped-init",
    "/assets/c4factory/js/doctype/part_list_import.js?v=20261121-palette-base-color-2",
    "/assets/c4factory/js/doctype/item_uom.js",
    "/assets/c4factory/js/doctype/part_list_versions.js",
    "/assets/c4factory/js/doctype/part_list_material_colors.js?v=20261121-color-palette",
    "/assets/c4factory/js/doctype/sales_order/item_colors.js?v=20261123-base-color-edit",
    # Register Sales Order actions independently of other apps' doctype_js hooks.
    "/assets/c4factory/js/doctype/sales_order/sales_order.js",
]

# ---------------------------------------------------------
# Client Scripts
# ---------------------------------------------------------

doctype_js = {
    "Pick List": "public/js/doctype/pick_list.js",
    "Stock Entry": "public/js/doctype/stock_entry.js",
    "BOM": "public/js/doctype/bom/bom_measurement_qty.js",
    "Work Order": "public/js/doctype/work_order.js",
    "Job Card": "public/js/doctype/job_card.js",

    "Sample Request": "public/js/doctype/sample_request/sample_request.js",
    "Project": "public/js/doctype/project.js",
    "Delivery Note": "public/js/doctype/delivery_note.js",
}

# ---------------------------------------------------------
# Doc Events (server hooks)
# ---------------------------------------------------------

doc_events = {
    "Project": {
        "onload": "c4factory.api.project_boq.onload",
        "validate": "c4factory.api.project_boq.validate_project",
    },
    "Delivery Note": {
        "before_validate": "c4factory.api.delivery_note_details.fill_delivery_note",
        "before_submit": "c4factory.api.project_boq.guard_delivery_change",
        "before_cancel": "c4factory.api.project_boq.guard_delivery_change",
        "on_submit": "c4factory.api.project_boq.sync_progress",
        "on_cancel": "c4factory.api.project_boq.sync_progress",
    },
    "Installation Note": {
        "validate": "c4factory.api.project_boq.validate_installation",
        "before_submit": "c4factory.api.project_boq.validate_installation",
        "on_submit": "c4factory.api.project_boq.sync_progress",
        "on_cancel": "c4factory.api.project_boq.sync_progress",
    },
    "PDS Request": {
        "on_update": "c4factory.api.project_boq.sync_progress",
        "on_cancel": "c4factory.api.project_boq.sync_progress",
    },
    "Part List": {
        "on_submit": "c4factory.api.project_boq.sync_progress",
        "on_update_after_submit": "c4factory.api.project_boq.sync_progress",
        "on_cancel": "c4factory.api.project_boq.sync_progress",
    },
	"Color sample": {
		"before_cancel": "c4factory.api.production_order.prevent_sample_cancel",
	},
    "*": {
        "before_validate": "c4factory.api.part_list_material_colors.validate_material_colors",
    },
    "Sales Order": {
        "on_update_after_submit": "c4factory.api.project_boq.sync_progress",
        "on_cancel": "c4factory.api.project_boq.sync_progress",
        "before_update_after_submit": "c4factory.api.sales_order_part_list.before_update_after_submit",
        "before_validate": [
            "c4factory.api.quotation_project_details.fill_sales_order",
            "c4factory.api.part_list_versions.set_sales_order_active_parts",
            "c4factory.api.sales_order_colors.validate_colors",
        ],
        "on_submit": [
            "c4factory.api.sales_order_project.on_submit",
            "c4factory.api.pds_request.on_sales_order_submit",
        ],
    },
    "BOM": {
        "before_validate": "c4factory.api.bom.calculate_item_qty",
    },
    "Item": {
        "validate": "c4factory.api.item_uom.validate_item_uoms",
    },
    # Work Order â€“ source warehouse autofill from Item Group
    "Work Order": {
        "validate": [
            "c4factory.c4_manufacturing.work_order_hooks.set_source_warehouse_from_item_group",
            "c4factory.c4_manufacturing.work_order_hooks.update_scrap_and_costing",
        ],
    },

    # Pick List custom flow
    "Pick List": {
        "before_validate": "c4factory.api.work_order_flow.on_pick_list_validate",
        "validate": "c4factory.api.work_order_flow.on_pick_list_validate",
        "on_submit": "c4factory.api.work_order_flow.on_pick_list_submit",
        "before_cancel": "c4factory.c4factory.doctype.sub_pick_list.sub_pick_list.prevent_main_pick_list_cancel",
        "on_cancel": "c4factory.api.work_order_flow.on_pick_list_cancel",
        "on_trash": "c4factory.api.work_order_flow.on_pick_list_trash",
    },

    # Stock Entry â€“ costing + WO update
    "Stock Entry": {
        "validate": [
            "c4factory.c4_manufacturing.stock_entry_hooks.validate_additional_material_transfer",
            "c4factory.c4_manufacturing.stock_entry_hooks.set_wip_target_warehouse",
        ],
        "before_submit": [
            "c4factory.c4_manufacturing.stock_entry_hooks.validate_additional_material_transfer",
            "c4factory.c4_manufacturing.stock_entry_hooks.set_wip_target_warehouse",
            "c4factory.c4_manufacturing.stock_entry_hooks.set_pick_list_transferred_production_qty",
        ],
        "on_submit": [
            "c4factory.c4_manufacturing.stock_entry_hooks.apply_additional_material_to_work_order",
            "c4factory.c4_manufacturing.stock_entry_hooks.on_submit_update_work_order_costing",
            "c4factory.api.work_order_flow.on_stock_entry_submit",
            "c4factory.c4factory.doctype.sub_pick_list.sub_pick_list.update_from_stock_entry",
        ],
        "on_cancel": [
            "c4factory.c4_manufacturing.stock_entry_hooks.reverse_additional_material_from_work_order",
            "c4factory.api.work_order_flow.on_stock_entry_cancel",
            "c4factory.c4factory.doctype.sub_pick_list.sub_pick_list.update_from_stock_entry",
        ],
        "on_trash": "c4factory.api.work_order_flow.on_stock_entry_trash",
    },

    # Job Card â€“ keep partial completion from becoming process loss
    "Job Card": {
        "before_validate": "c4factory.c4_manufacturing.job_card_hooks.set_operation_row_reference",
        "validate": "c4factory.c4_manufacturing.job_card_hooks.set_operation_row_reference",
        "before_submit": [
            "c4factory.c4_manufacturing.job_card_hooks.set_operation_row_reference",
            "c4factory.c4_manufacturing.job_card_hooks.normalize_partial_completion",
        ],
        "on_update": "c4factory.c4_manufacturing.job_card_hooks.sync_work_order_costing_from_job_card",
        "on_update_after_submit": "c4factory.c4_manufacturing.job_card_hooks.sync_work_order_costing_from_job_card",
        "on_submit": "c4factory.c4_manufacturing.job_card_hooks.sync_work_order_costing_from_job_card",
        "on_cancel": "c4factory.c4_manufacturing.job_card_hooks.sync_work_order_costing_from_job_card",
    },
}

# ---------------------------------------------------------
# Whitelisted method / class overrides
# ---------------------------------------------------------

# Do NOT override Work Order.make_stock_entry here.
# We keep the original finished-goods costing logic from c4pricing.
override_doctype_class = {
    "Work Order": "c4factory.overrides.work_order.WorkOrder",
    "Stock Entry": "c4factory.overrides.stock_entry.StockEntry",
}

# ---------------------------------------------------------
# Database patches for custom fields
# ---------------------------------------------------------

patches = [
    # Work Order scrap & costing fields
    "c4factory.patches.v1_0.setup_work_order_custom_fields",
    # WO / Pick List / Stock Entry extra fields (includes custom_pl_qty)
    "c4factory.patches.v1_0.setup_wo_pl_se_custom_fields",
    # Pick List real operation cost from linked Job Cards
    "c4factory.patches.v1_0.setup_pick_list_operation_cost_fields",
    # Allow users to close a partial Pick List and waive its remainder
    "c4factory.patches.v1_0.setup_manual_pick_list_completion",
    # Additional material transfers linked to a Pick List and Work Order
    "c4factory.patches.v1_0.setup_additional_material_flow",
    "c4factory.patches.v1_0.setup_sub_pick_list_stock_fields",
    "c4factory.patches.v1_0.setup_work_order_additional_material_table",
    "c4factory.patches.v1_0.setup_continuous_start_transfer",
    "c4factory.patches.v1_0.setup_continuous_start_pick_list_field",
    "c4factory.patches.v1_0.setup_continuous_start_qty_field",
    "c4factory.patches.v1_0.setup_bom_spec_fields",
]

override_doctype_dashboards = {
	"Color sample": "c4factory.api.color_sample_dashboard.get_data",
    "Project": "c4factory.api.project_dashboard.get_data",
    "BOM": "c4factory.api.bom_dashboard.get_data",
    "Pick List": "c4factory.api.pick_list_dashboard.get_data",
    "Sales Order": "c4factory.api.sales_order_dashboard.get_data",
    "Sub Pick List": "c4factory.api.sub_pick_list_dashboard.get_data",
    "Work Order": "c4factory.api.work_order_dashboard.get_data",
}

# ---------------------------------------------------------
# Whitelisted method overrides
# ---------------------------------------------------------

override_whitelisted_methods = {
    "erpnext.manufacturing.doctype.work_order.work_order.create_pick_list": (
        "c4factory.api.work_order_pick_list.create_pick_list"
    ),
    "erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry": (
        "c4factory.api.work_order_stock.make_stock_entry"
    ),
}
