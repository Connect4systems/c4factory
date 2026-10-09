from frappe import _

from erpnext.projects.doctype.project.project_dashboard import get_data as get_core_data


def get_data(*args, **kwargs):
	data = get_core_data()
	data.setdefault("non_standard_fieldnames", {})["Color sample"] = "project"
	data.setdefault("transactions", []).append({"label": _("Color Samples"), "items": ["Color sample"]})
	return data
