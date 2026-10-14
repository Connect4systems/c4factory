from frappe import _


def get_data(*args, **kwargs):
	return {"fieldname": "color_sample", "transactions": [
		{"label": _("Manufacturing"), "items": ["Production Order"]},
	]}
