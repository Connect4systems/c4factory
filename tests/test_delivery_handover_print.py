"""Render the actual print template with representative transaction data."""
import unittest
from pathlib import Path
from types import SimpleNamespace

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from test_delivery_note_details import Delivery
from test_project_boq import Doc


TEMPLATE = Path(__file__).resolve().parents[1] / "c4factory/c4factory/print_format/delivery_handover/delivery_handover.html"


class Item(Doc):
    def get_formatted(self, field, parent):
        return str(self[field])


def render_handover(rows=None, item_values=None, **values):
    row = Item(item_code="C-1138334", item_name="Coffee table", qty=1,
        description="<p>Top made of MDF 25mm; stainless steel structure.</p>",
        so_detail="SO-ROW-1", against_sales_order="SO-001",
        custom_note="ملاحظات المستلم", project="PROJ-0001")
    item = Doc(custom_material_line="HPL,Metal", image="")
    if item_values is not None:
        item = Doc(item_values)
    company = Doc(company_logo="", phone_no="020000000", email="info@example.com", website="example.com")
    doc = Delivery(name="DN-2026-00448", company="شركة الأثاث", customer="CUST-001",
        customer_name="بنك التنمية الصناعية", custom_project_title="المركز الرئيسي - الدور الثامن",
        project="PROJ-0001", posting_date="2026-11-22", items=rows if rows is not None else [row])
    doc.update(values)
    def get_doc(doctype, name):
        if doctype == "Company":
            return company
        if doctype == "Item":
            return item
        raise AssertionError(f"Print must fetch materials from Item, not {doctype}")

    frappe = SimpleNamespace(
        get_doc=get_doc,
        db=SimpleNamespace(get_value=lambda dt, name, field: "P-8716" if dt == "Project" else None),
        utils=SimpleNamespace(formatdate=lambda value, pattern: "22/11/2026"))
    # StrictUndefined makes accidental access to unavailable helpers fail here.
    env = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined)
    return env.from_string(TEMPLATE.read_text(encoding="utf-8")).render(
        doc=doc, frappe=frappe)


class TestDeliveryHandoverPrint(unittest.TestCase):
    def test_print_uses_dn_number_customer_title_and_project_business_number(self):
        html = render_handover()
        for text in ("DN-2026-00448", "بنك التنمية الصناعية - المركز الرئيسي - الدور الثامن", "P-8716"):
            self.assertIn(text, html)
        self.assertNotIn(">PROJ-0001<", html)

    def test_uses_edited_delivery_note_and_item_material_line(self):
        html = render_handover()
        for text in ("ملاحظات المستلم", "HPL,Metal", 'class="handover-materials"'):
            self.assertIn(text, html)
        self.assertNotIn("Original order note", html)

    def test_item_materials_use_archi_labels_and_hide_empty_fields(self):
        html = render_handover(item_values={"custom_material_line": "HPL", "custom_wood": "Oak",
            "custom_metal": "Steel", "custom_glass": "Clear", "custom_fabric": "Linen"})
        for label, value in [("Material", "HPL"), ("Wood", "Oak"), ("Metal", "Steel"),
                ("Glass", "Clear"), ("Fabric", "Linen")]:
            self.assertIn(f'class="handover-material-label">{label}</span>', html)
            self.assertIn(f'<span dir="auto">{value}</span>', html)
        self.assertNotIn('class="handover-material-label">Other</span>', html)

    def test_material_line_fetched_for_item_without_sales_order_reference(self):
        row = Item(item_code="A", item_name="A", qty=1, description="", custom_material_line="Stale row material")
        html = render_handover(rows=[row], item_values={"custom_material_line": "Item master material"})
        self.assertIn("Item master material", html)
        self.assertNotIn("Stale row material", html)

    def test_missing_item_materials_and_html_characters(self):
        html = render_handover(item_values={})
        self.assertNotIn('class="handover-material-label">', html)
        html = render_handover(item_values={"custom_material_line": "<unsafe>"})
        self.assertIn("&lt;unsafe&gt;", html)

    def test_free_text_escaped_and_unlinked_items_render(self):
        row = Item(item_code="A", item_name="A", qty=2, description="", custom_note="<script>bad()</script>")
        html = render_handover(rows=[row], custom_project_title="<unsafe>")
        self.assertIn("&lt;script&gt;bad()&lt;/script&gt;", html)
        self.assertIn("&lt;unsafe&gt;", html)
        self.assertIn(">2</td>", html)

    def test_empty_optional_details_and_empty_items_render(self):
        html = render_handover(rows=[], project=None, custom_project_title=None)
        self.assertIn("محضر استلام نهائي", html)
