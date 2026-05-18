from frappe import _


def get_data(*args, **kwargs):
    return {
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
