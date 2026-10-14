import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from test_part_list_save import ROOT, load_module


class Doc(dict):
	def __getattr__(self, key):
		return self.get(key)

	def __setattr__(self, key, value):
		self[key] = value

	def set(self, key, value):
		self[key] = value


def field(name, kind="Data", options=None):
	return Doc(fieldname=name, fieldtype=kind, options=options)


class TestPartListVersions(unittest.TestCase):
	def setUp(self):
		self.frappe = ModuleType("frappe")
		self.frappe._ = lambda value: value
		self.frappe.whitelist = lambda: lambda fn: fn
		self.frappe.has_permission = Mock(return_value=True)
		self.frappe.PermissionError = PermissionError
		self.frappe.throw = Mock(side_effect=ValueError)
		for name in ("db", "get_doc", "get_all", "get_list", "get_meta"):
			setattr(self.frappe, name, Mock())
		utils = ModuleType("frappe.utils")
		utils.cint = lambda value: int(value or 0)
		utils.flt = lambda value: float(value or 0)
		utils.now_datetime = lambda: "NOW"
		self.modules = patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": utils})
		self.modules.start()
		self.addCleanup(self.modules.stop)
		self.api = load_module("c4factory/api/part_list_versions.py", "versions_test")
		self.source = Doc(name="CUBE-01", docstatus=1, disable=0, product="CUBE",
			material_line="Custom Line", check_permission=Mock(), version_of="OLDER",
			meta=SimpleNamespace(fields=[field("product"), field("material_line"), field("version_of"),
				field("pds_table", "Table"), field("panel_materials", "Table"), field("sales_tab", "Tab Break")]),
			pds_table=[Doc(name="old-row", parent="CUBE-01", title="Drawing", arttach="/private/files/design.pdf",
				meta=SimpleNamespace(fields=[field("title"), field("arttach", "Attach")]))],
			panel_materials=[Doc(name="old-panel", material="MDF", qty=3,
				meta=SimpleNamespace(fields=[field("material", "Link"), field("qty", "Float")]))])
		self.frappe.get_doc.return_value = self.source

	def test_copy_preserves_every_table_value_and_file_link_without_identities(self):
		values = self.api.get_copy_payload("CUBE-01", new_version=1)["values"]
		self.assertEqual(values["pds_table"], [{"title": "Drawing", "arttach": "/private/files/design.pdf"}])
		self.assertEqual(values["panel_materials"], [{"material": "MDF", "qty": 3}])
		self.assertEqual(values["material_line"], "Custom Line")
		self.assertNotIn("name", values)
		self.assertNotIn("version_of", values)
		self.source.check_permission.assert_called_once_with("read")

	def test_new_version_rejects_draft_and_copy_requires_create_permission(self):
		self.source.docstatus = 0
		with self.assertRaises(ValueError):
			self.api.get_copy_payload("CUBE-01", new_version=1)
		self.frappe.has_permission.return_value = False
		with self.assertRaises(ValueError):
			self.api.get_copy_payload("CUBE-01")

	def test_import_rejects_submitted_target_and_self_import(self):
		target = Doc(docstatus=1, check_permission=Mock())
		self.frappe.get_doc.side_effect = [self.source, target]
		with self.assertRaises(ValueError):
			self.api.get_copy_payload("CUBE-01", target="TARGET")
		self.frappe.get_doc.side_effect = [self.source, self.source]
		with self.assertRaises(ValueError):
			self.api.get_copy_payload("CUBE-01", target="CUBE-01")

	def test_selector_filters_on_part_list_overrides_and_treats_zero_as_unset(self):
		part = Doc(name="CUBE-01", product="CUBE", product_name="Table", description="Custom description",
			product_image="custom.png", material_line="Custom Line", width=80, hight=40, depth=60)
		item = Doc(name="CUBE", item_name="Table", item_group="Tables", brand="Brand", image="item.png", stock_uom="Nos")
		self.frappe.get_list.side_effect = [[part], [item]]
		with patch.object(self.api, "allowed_item_groups", return_value=["Tables"]):
			result = self.api.get_selector_items("Standard Lines", material_line="Custom Line", width=0, height=0, txt="custom")
		self.assertEqual(result["total"], 1)
		self.assertEqual(result["items"][0]["image"], "custom.png")
		self.assertEqual(result["items"][0]["width"], 80)

	def test_selector_rejects_unrelated_group(self):
		with patch.object(self.api, "allowed_item_groups", return_value=["Tables"]):
			self.assertEqual(self.api.get_selector_items("Standard Lines", item_group="Other")["total"], 0)
		self.frappe.get_list.assert_not_called()

	def test_activation_repoints_both_live_parent_types_and_preserves_cancelled_records(self):
		self.source.is_default = 1
		meta = SimpleNamespace(fields=[field("part_list", "Link", "Part List")], has_field=lambda name: True)
		self.frappe.get_meta.return_value = meta
		self.frappe.get_all.side_effect = [["OLD"], [
			Doc(name="SO-row", parent="SO", part_list="OLD"), Doc(name="cancel-row", parent="CANCEL", part_list="OLD"),
		], [Doc(name="PDS-row", parent="PDS", part_list="OLD")]]
		self.frappe.db.get_value.side_effect = lambda doctype, name, attr: 2 if name == "CANCEL" else 1
		colors = ModuleType("c4factory.api.sales_order_colors")
		colors.get_part_list_colors = Mock(return_value={"rows": [{"source_row": "new-panel"}]})
		with patch.dict(sys.modules, {"c4factory.api.sales_order_colors": colors}):
			self.api.activate_for_product(self.source)
		calls = self.frappe.db.set_value.call_args_list
		updates = {(call.args[0], call.args[1]): call.args[2] for call in calls}
		self.assertEqual(updates[("PDS Request Item", "PDS-row")], {"part_list": "CUBE-01"})
		self.assertEqual(updates[("Sales Order Item", "SO-row")]["part_list"], "CUBE-01")
		self.assertIn("new-panel", updates[("Sales Order Item", "SO-row")]["custom_color_sample_data"])
		self.assertNotIn(("Sales Order Item", "cancel-row"), updates)
		self.assertFalse(any(call.args[0] == "Color Sample Item" for call in calls))
		self.frappe.db.set_value.assert_any_call("Part List", "OLD", "is_default", 0)

	def test_api_created_sales_order_resolves_active_product(self):
		self.frappe.get_meta.return_value = SimpleNamespace(fields=[field("part_list", "Link", "Part List")])
		self.frappe.get_all.return_value = [Doc(product="CUBE", name="CUBE-02")]
		row = Doc(item_code="CUBE", part_list="CUBE-01")
		self.api.set_sales_order_active_parts(SimpleNamespace(docstatus=0, items=[row]))
		self.assertEqual(row.part_list, "CUBE-02")

	def test_private_pds_attachment_is_relinked_to_copy(self):
		self.frappe.db.exists.return_value = False
		self.frappe.get_all.return_value = [Doc(name="FILE")]
		file = Doc(file_name="design.pdf", file_url="/private/files/design.pdf", is_private=1, check_permission=Mock())
		new_file = Mock()
		self.frappe.get_doc.side_effect = [file, new_file]
		self.api.link_copied_attachments(self.source)
		values = self.frappe.get_doc.call_args.args[0]
		self.assertEqual(values["attached_to_name"], "CUBE-01")
		self.assertEqual(values["file_url"], file.file_url)
		file.check_permission.assert_called_once_with("read")
		new_file.insert.assert_called_once_with(ignore_permissions=True)

	def test_sales_specs_removed_and_material_line_editable(self):
		meta = json.loads((ROOT / "c4factory/c4factory/doctype/part_list/part_list.json").read_text())
		fields = {field["fieldname"]: field for field in meta["fields"]}
		self.assertNotIn("sales_spcs_tab", fields)
		for name in ("material_line", "metal_material_line"):
			self.assertFalse(fields[name].get("read_only"))
			self.assertNotIn("fetch_from", fields[name])


if __name__ == "__main__":
	unittest.main()
