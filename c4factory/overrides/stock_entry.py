import frappe
from frappe.utils import flt
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry as ERPNextStockEntry


class StockEntry(ERPNextStockEntry):
    def check_if_operations_completed(self):
        if self.work_order and flt(
            frappe.db.get_value("Work Order", self.work_order, "custom_disable_operation")
        ):
            return

        return super().check_if_operations_completed()
