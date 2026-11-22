"""Render the actual print template with representative transaction data."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from jinja2.sandbox import SandboxedEnvironment

from test_delivery_note_details import Delivery
from test_project_boq import Doc


TEMPLATE = Path(__file__).resolve().parents[1] / "c4factory/c4factory/print_format/delivery_handover/delivery_handover.html"


class Item(Doc):
    def get_formatted(self, field, parent):
        return str(self[field])


def render_handover(rows=None, **values):
    row = Item(item_code="C-1138334", item_name="Coffee table", qty=1,
        description="<p>Top made of MDF 25mm; stainless steel structure.</p>",
        so_detail="SO-ROW-1", against_sales_order="SO-001",
        custom_note="ملاحظات المستلم", project="PROJ-0001")
    source = Doc(parent="SO-001", item_code="C-1138334", custom_note="Original order note",
        custom_color_sample_data=json.dumps({"rows": [
            {"source_table": "panel_materials", "color": "دوكو هاي جلوس"},
            {"source_table": "metal_material", "color": "استانلس"}]}))
    company = Doc(company_logo="", phone_no="020000000", email="info@example.com", website="example.com")
    doc = Delivery(name="DN-2026-00448", company="شركة الأثاث", customer="CUST-001",
        customer_name="بنك التنمية الصناعية", custom_project_title="المركز الرئيسي - الدور الثامن",
        project="PROJ-0001", posting_date="2026-11-22", items=rows if rows is not None else [row])
    doc.update(values)
    frappe = SimpleNamespace(
        get_doc=lambda dt, name: company if dt == "Company" else source,
        db=SimpleNamespace(get_value=lambda dt, name, field: "P-8716" if dt == "Project" else None),
        parse_json=json.loads,
        utils=SimpleNamespace(formatdate=lambda value, pattern: "22/11/2026"))
    env = SandboxedEnvironment(autoescape=False)
    return env.from_string(TEMPLATE.read_text(encoding="utf-8")).render(doc=doc, frappe=frappe)


class TestDeliveryHandoverPrint(unittest.TestCase):
    def test_print_uses_dn_number_customer_title_and_project_business_number(self):
        html = render_handover()
        for text in ("DN-2026-00448", "بنك التنمية الصناعية - المركز الرئيسي - الدور الثامن", "P-8716"):
            self.assertIn(text, html)
        self.assertNotIn(">PROJ-0001<", html)

    def test_uses_edited_delivery_note_and_sales_order_materials(self):
        html = render_handover()
        for text in ("ملاحظات المستلم", "دوكو هاي جلوس", "استانلس"):
            self.assertIn(text, html)
        self.assertNotIn("Original order note", html)

    def test_free_text_escaped_and_unlinked_items_render(self):
        row = Item(item_code="A", item_name="A", qty=2, description="", custom_note="<script>bad()</script>")
        html = render_handover(rows=[row], custom_project_title="<unsafe>")
        self.assertIn("&lt;script&gt;bad()&lt;/script&gt;", html)
        self.assertIn("&lt;unsafe&gt;", html)
        self.assertIn(">2</td>", html)

    def test_empty_optional_details_and_empty_items_render(self):
        html = render_handover(rows=[], project=None, custom_project_title=None)
        self.assertIn("محضر استلام نهائي", html)
