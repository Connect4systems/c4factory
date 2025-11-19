app_name = "c4factory"
app_title = "C4Factory"
app_publisher = "Connect 4 Systems"
app_description = "Factory App"
app_email = "info@connect4systems.com"
app_license = "mit"


doctype_js = {
    "Work Order": "public/js/doctype/work_order.js",
    "Pick List": "public/js/doctype/pick_list.js",
    "BOM": "public/js/doctype/bom/bom_measurement_qty.js",
}

# Doc Events (server hooks)
doc_events = {
    "Work Order": {
        "before_insert": [
            "c4factory.c4_manufacturing.work_order_hooks.copy_scrap_from_bom",
            "c4factory.c4_manufacturing.work_order_hooks.copy_required_items_from_bom",
        ],
        "validate": "c4factory.c4_manufacturing.work_order_hooks.update_scrap_and_costing",
        "on_update_after_submit": "c4factory.c4_manufacturing.work_order_hooks.calculate_required_items_balance",
    },
    "Pick List": {
        "validate": "c4factory.c4_manufacturing.pick_list_hooks.validate_pick_list",
        "on_submit": "c4factory.c4_manufacturing.pick_list_hooks.on_submit_update_work_order",
        "on_cancel": "c4factory.c4_manufacturing.pick_list_hooks.on_cancel_update_work_order",
    },
    "Stock Entry": {
        "validate": "c4factory.c4_manufacturing.stock_entry_hooks.set_wip_target_warehouse",
        "on_submit": "c4factory.c4_manufacturing.stock_entry_hooks.on_submit_update_work_order_costing",
        "on_cancel": "c4factory.c4_manufacturing.stock_entry_hooks.on_cancel_update_pick_list",
    },
}

# Override ERPNext's make_stock_entry for Work Order (Finish logic)
override_whitelisted_methods = {
    "erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry":
        "c4factory.api.work_order_stock.make_stock_entry",
}

# Database patches for custom fields
patches = [
    "c4factory.patches.v1_0.setup_work_order_custom_fields",
    "c4factory.patches.v1_0.setup_pick_list_custom_fields",
]
.