from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder as ERPNextWorkOrder
import frappe
from frappe.utils import flt


class WorkOrder(ERPNextWorkOrder):
  """
  Custom Work Order for c4factory.

  Goal:
  - First time: when there are NO required_items, use ERPNext logic to
    populate from BOM.
  - After that: if required_items already has rows, do not rebuild or
    reset them automatically, so the user can freely edit required_qty,
    add or remove rows.
  - Provide a stronger `set_status` implementation that follows the
    standard status list while preserving other logic.
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

  def set_status(self):
    """
    Compute Work Order `status` to follow the standard sequence:
    Draft, Submitted, Not Started, In Process, Completed, Stopped, Closed, Cancelled.

    - Keep `Stopped` and `Closed` if already set.
    - Use `Draft` when docstatus == 0, `Cancelled` when docstatus == 2.
    - For submitted docs, decide between Not Started / In Process / Completed
      based on produced qty, transferred material, and operations.
    """
    try:
      super().set_status()
    except Exception:
      # If core set_status is unavailable or errors, continue with our logic
      pass

    # Determine base status from docstatus first
    docstatus = getattr(self, "docstatus", 0)
    if docstatus == 0:
      new_status = "Draft"
    elif docstatus == 2:
      new_status = "Cancelled"
    else:
      # Preserve explicit stopped/closed states
      current = (getattr(self, "status", None) or "")
      if current in ("Stopped", "Closed"):
        new_status = current
      else:
        qty = flt(getattr(self, "qty", 0))
        produced = flt(getattr(self, "produced_qty", 0))
        transferred = flt(getattr(self, "material_transferred_for_manufacturing", 0))

        # Check operations for any progress/completed work
        in_process = False
        for op in (getattr(self, "operations") or []):
          if flt(op.get("completed_qty") or 0) > 0 or flt(op.get("progress") or 0) > 0:
            in_process = True
            break

        if qty and produced >= qty:
          new_status = "Completed"
        elif transferred > 0 or produced > 0 or in_process:
          new_status = "In Process"
        else:
          # When submitted but nothing started
          new_status = "Not Started"

    # Apply status if changed
    if getattr(self, "status", None) != new_status:
      self.status = new_status
      # Persist immediately when the document exists in DB
      if getattr(self, "name", None):
        try:
          frappe.db.set_value(
            "Work Order",
            self.name,
            "status",
            new_status,
            update_modified=False,
          )
        except Exception:
          frappe.log_error(frappe.get_traceback(), "C4Factory: WorkOrder.set_status db_set failed")
