from frappe import _

from erpnext.selling.doctype.sales_order.sales_order_dashboard import get_data as get_core_data


def get_data(*args, **kwargs):
	data = get_core_data()
	data.setdefault("non_standard_fieldnames", {})["Contract BOM Request"] = "sales_order"

	transactions = data.setdefault("transactions", [])
	manufacturing_group = next(
		(group for group in transactions if group.get("label") == _("Manufacturing")),
		None,
	)
	if not manufacturing_group:
		manufacturing_group = {"label": _("Manufacturing"), "items": []}
		transactions.append(manufacturing_group)

	items = manufacturing_group.setdefault("items", [])
	if "Contract BOM Request" not in items:
		items.append("Contract BOM Request")

	return data
