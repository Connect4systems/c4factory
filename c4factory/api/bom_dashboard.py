from frappe import _

from erpnext.manufacturing.doctype.bom.bom_dashboard import get_data as get_core_data


def get_data(*args, **kwargs):
    data = get_core_data()
    data.setdefault("non_standard_fieldnames", {})["Item Coding Request"] = "bom"

    transactions = data.setdefault("transactions", [])
    group = next(
        (group for group in transactions if group.get("label") == _("Manufacturing")),
        None,
    )
    if group is None:
        group = {"label": _("Manufacturing"), "items": []}
        transactions.append(group)

    items = group.setdefault("items", [])
    if "Item Coding Request" not in items:
        items.append("Item Coding Request")

    return data
