import frappe
from frappe.utils import flt


def normalize_partial_completion(doc, method=None):
    """
    Prevent auto process loss on partial Job Card completion.

    ERPNext may infer process_loss_qty as (for_quantity - completed_qty)
    when users submit a partially completed Job Card as Completed.
    For C4 flow we treat the remaining quantity as pending work, not loss.
    """
    qty = flt(getattr(doc, "for_quantity", 0))
    completed = flt(getattr(doc, "total_completed_qty", 0))
    process_loss = flt(getattr(doc, "process_loss_qty", 0))

    if qty <= 0 or completed <= 0 or completed >= qty:
        return

    remaining = max(qty - completed, 0.0)

    # Only normalize the common auto-inferred case.
    if abs(process_loss - remaining) > 0.000001:
        return

    doc.process_loss_qty = 0.0

    if hasattr(doc, "process_loss_percentage"):
        doc.process_loss_percentage = 0.0

    # Convert this Job Card into a true partial-complete card.
    # Remaining quantity stays pending on the Work Order.
    doc.for_quantity = completed


def sync_work_order_costing_from_job_card(doc, method=None):
    """
    Keep Work Order c4_operating_cost / c4_total_cost synced with
    actual Job Card operating data whenever Job Cards change.
    """
    wo_name = getattr(doc, "work_order", None)
    if not wo_name:
        return

    try:
        from c4factory.c4_manufacturing.stock_entry_hooks import recompute_work_order_costing

        recompute_work_order_costing(wo_name)
    except Exception:
        # Do not block Job Card save/submit due to costing sync issues.
        frappe.log_error(frappe.get_traceback(), "C4Factory: Job Card costing sync failed")
