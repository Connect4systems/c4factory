from frappe import _


def get_data():
	return {
		"internal_links": {"Part List": ["items", "part_list"]},
		"transactions": [{"label": _("Manufacturing"), "items": ["Part List"]}],
	}
