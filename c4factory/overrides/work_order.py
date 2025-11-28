from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder as ERPNextWorkOrder


class WorkOrder(ERPNextWorkOrder):
    """
    Custom Work Order for c4factory.

    Goal:
    - First time: when there are NO required_items, use ERPNext logic to
      populate from BOM.
    - After that: if required_items already has rows, do not rebuild or
      reset them automatically, so the user can freely edit required_qty,
      add or remove rows.
    """

    def set_required_items(self, reset_only_qty: bool = False):  # signature must match core
        """
        ERPNext sometimes calls set_required_items(reset_only_qty=True).
        We accept the same argument, but if rows already exist we do nothing.
        """

        # If there are no rows yet, use standard behaviour (populate from BOM)
        if not self.get("required_items"):
            return super().set_required_items(reset_only_qty=reset_only_qty)

        # If rows already exist:
        # - when reset_only_qty is True, core would normally recompute required_qty.
        # - we skip this to keep the user edits.
        return
