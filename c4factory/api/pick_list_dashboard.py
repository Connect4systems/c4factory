from frappe import _


def get_data(*args, **kwargs):
    return {
        "fieldname": "pick_list",
        "non_standard_fieldnames": {
            "Job Card": "custom_pick_list",
        },
        "transactions": [
            {
                "label": _("Manufacturing"),
                "items": ["Job Card", "Stock Entry"],
            },
            {
                "label": _("Sales"),
                "items": ["Sales Order", "Delivery Note"],
            },
            {
                "label": _("Stock"),
                "items": ["Stock Reservation Entry"],
            },
        ],
    }
