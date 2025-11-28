# c4factory/hooks.py

app_name = "c4factory"
app_title = "C4Factory"
app_publisher = "Connect 4 Systems"
app_description = "Factory App"
app_email = "info@connect4systems.com"
app_license = "mit"

# ---------------------------------------------------------
# Client Scripts
# ---------------------------------------------------------

doctype_js = {
    "Pick List": "public/js/doctype/pick_list.js",
    "BOM": "public/js/doctype/bom/bom_measurement_qty.js",
    "Work Order": "public/js/doctype/work_order.js",
}


# ---------------------------------------------------------
# Doc Events (server hooks)
# ---------------------------------------------------------

doc_events = {
    # ... your other hooks ...

    "Pick List": {
        "validate": "c4factory.api.work_order_flow.on_pick_list_validate",
        "on_submit": "c4factory.api.work_order_flow.on_pick_list_submit",
        "on_cancel": "c4factory.api.work_order_flow.on_pick_list_cancel",
    },

    "Stock Entry": {
        "validate": "c4factory.c4_manufacturing.stock_entry_hooks.set_wip_target_warehouse",
        "on_submit": [
            "c4factory.c4_manufacturing.stock_entry_hooks.on_submit_update_work_order_costing",
            "c4factory.api.work_order_flow.on_stock_entry_submit",
        ],
        "on_cancel": "c4factory.api.work_order_flow.on_stock_entry_cancel",
    },
}


# ---------------------------------------------------------
# Whitelisted method overrides
# ---------------------------------------------------------

# Do NOT override Work Order.make_stock_entry here.
# We keep the original finished-goods costing logic from c4pricing.
override_doctype_class = {

    "Work Order": "c4factory.overrides.work_order.WorkOrder",
}

# ---------------------------------------------------------
# Database patches for custom fields
# ---------------------------------------------------------

patches = [
    # Work Order scrap & costing fields
    "c4factory.patches.v1_0.setup_work_order_custom_fields",
    # WO / Pick List / Stock Entry extra fields (includes custom_pl_qty)
    "c4factory.patches.v1_1.setup_wo_pl_se_custom_fields",
]
